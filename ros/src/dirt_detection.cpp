#include <autopnp_dirt_detection/dirt_detection.h>

using namespace ipa_DirtDetection;
using namespace std;
using namespace cv;

//////////////////
///Constructor///
/////////////////

DirtDetection::DirtDetection(ros::NodeHandle node_handle)
: node_handle_(node_handle)
{
	it_ = 0;

	Image_buffer_size = 5;
}

/////////////////
///Destructor///
////////////////

DirtDetection::~DirtDetection()
{
	if (it_ != 0) delete it_;
}

/////////////////////////
///Create subscribers///
///////////////////////

void DirtDetection::init()
{
	it_ = new image_transport::ImageTransport(node_handle_);
//	color_camera_image_sub_ = it_->subscribe("camera/rgb/image_color", 1, boost::bind(&DirtDetection::imageDisplayCallback, this, _1));
	camera_depth_points_sub_ =  node_handle_.subscribe<sensor_msgs::PointCloud2>("/camera/rgb/points", 1, &DirtDetection::planeDetectionCallback, this);
}

/////////////////////
///Main functions///
///////////////////

int main(int argc, char **argv)
{
	ros::init(argc, argv, "dirt_detection");

	ros::NodeHandle n;

	DirtDetection id(n);
	id.init();



	//start to look for messages (loop)
	ros::spin();

	return 0;
}

/////////////////////////
///Callback functions///
///////////////////////

void DirtDetection::imageDisplayCallback(const sensor_msgs::ImageConstPtr& color_image_msg)
{
	cv_bridge::CvImageConstPtr color_image_ptr;
	cv::Mat color_image;
	//convert message to cv::Mat
	convertColorImageMessageToMat(color_image_msg, color_image_ptr, color_image);

	DirtDetection::SaliencyDetection_C3(color_image);
}

void DirtDetection::planeDetectionCallback(const sensor_msgs::PointCloud2ConstPtr& point_cloud2_rgb_msg)
{

	pcl::PointCloud<pcl::PointXYZRGB>::Ptr input_cloud(new pcl::PointCloud<pcl::PointXYZRGB>());
	DirtDetection::convertPointCloudMessageToPointCloudPcl(point_cloud2_rgb_msg, input_cloud);

	DirtDetection::planeDetection(input_cloud);

}

////////////////////////
///Convert functions///
//////////////////////

void DirtDetection::convertPointCloudMessageToPointCloudPcl(const sensor_msgs::PointCloud2ConstPtr& point_cloud2_rgb_msg, pcl::PointCloud<pcl::PointXYZRGB>::Ptr &point_cloud_XYZRGB)
{
	//conversion Ros message->Pcl point cloud
	pcl::fromROSMsg(*point_cloud2_rgb_msg, *point_cloud_XYZRGB);
}


unsigned long DirtDetection::convertColorImageMessageToMat(const sensor_msgs::Image::ConstPtr& color_image_msg, cv_bridge::CvImageConstPtr& color_image_ptr, cv::Mat& color_image)
{
	try
	{
		color_image_ptr = cv_bridge::toCvShare(color_image_msg, sensor_msgs::image_encodings::BGR8);
	}
	catch (cv_bridge::Exception& e)
	{
		ROS_ERROR("DirtDetection: cv_bridge exception: %s", e.what());
		return 1;
	}
	color_image = color_image_ptr->image;

	return 0;
}


void DirtDetection::planeDetection(pcl::PointCloud<pcl::PointXYZRGB>::Ptr input_cloud)
{

	//recreate original color image from point cloud
	cv::Mat color_image = cv::Mat::zeros(input_cloud->height, input_cloud->width, CV_8UC3);
	int index = 0;
	for (int v=0; v<input_cloud->height; v++)
	{
		for (int u=0; u<input_cloud->width; u++, index++)
		{
			pcl::PointXYZRGB point = (*input_cloud)[index];
			bgr bgr_ = {point.b, point.g, point.r};
			color_image.at<bgr>(v, u) = bgr_;
		}
	}

	//display original image
	cv::imshow("color image", color_image);


	// Create the segmentation object for the planar model and set all the parameters
	pcl::SACSegmentation<pcl::PointXYZRGB> seg;
	pcl::PointIndices::Ptr inliers (new pcl::PointIndices);
	pcl::ModelCoefficients::Ptr coefficients (new pcl::ModelCoefficients);

	pcl::PCDWriter writer;
	seg.setOptimizeCoefficients (true);
	seg.setModelType (pcl::SACMODEL_PLANE);
	seg.setMethodType (pcl::SAC_RANSAC);
	seg.setMaxIterations (100);
	seg.setDistanceThreshold (0.02);

	seg.setInputCloud(input_cloud);
	seg.segment (*inliers, *coefficients);

	if (inliers->indices.size () != 0) //check if ground/floor detected
	{

		cv::Mat ground_image = cv::Mat::zeros(input_cloud->height, input_cloud->width, CV_8UC3);
		cv::Mat ground_mask = cv::Mat::zeros(input_cloud->height, input_cloud->width, CV_8UC1);
		for (size_t i=0; i<inliers->indices.size(); i++)
		{
			int v = inliers->indices[i]/input_cloud->width;	// check ob das immer abrundet
			int u = inliers->indices[i] - v*input_cloud->width;

			pcl::PointXYZRGB point = (*input_cloud)[(inliers->indices[i])];
			bgr bgr_ = {point.b, point.g, point.r};
			ground_image.at<bgr>(v, u) = bgr_;
			ground_mask.at<uchar>(v, u) = 255;
		}

		//display detected floor
//		cv::imshow("floor cropped", ground_image);

		//detect dirt on the floor
		DirtDetection::SaliencyDetection_C3(ground_image, &ground_mask);

	}


}

void DirtDetection::SaliencyDetection_C1(cv::Mat& one_channel_image, cv::Mat& result_image)
{
	int scale = 6;

	//given a one channel image
	unsigned int size = (int)floor((float)pow(2.0,scale)); //the size to do the saliency at

	//create different images
	cv::Mat bw_im;
	cv::resize(one_channel_image,bw_im,cv::Size(size,size));

	cv::Mat realInput(size,size, CV_32FC1);
	cv::Mat imaginaryInput(size,size, CV_32FC1);
	cv::Mat complexInput(size,size, CV_32FC2);

	bw_im.convertTo(realInput,CV_32F,1.0/255,0);
	imaginaryInput = cv::Mat::zeros(size,size,CV_32F);

	std::vector<cv::Mat> vec;
	vec.push_back(realInput);
	vec.push_back(imaginaryInput);
	cv::merge(vec, complexInput);

	cv::Mat dft_A(size,size,CV_32FC2);

	cv::dft(complexInput, dft_A, cv::DFT_COMPLEX_OUTPUT,size);
	vec.clear();
	cv::split(dft_A,vec);
	realInput = vec[0];
	imaginaryInput = vec[1];

	// Compute the phase angle
	cv::Mat image_Mag(size,size, CV_32FC1);
	cv::Mat image_Phase(size,size, CV_32FC1);

	//compute the phase of the spectrum
	cv::cartToPolar(realInput, imaginaryInput, image_Mag, image_Phase,0);

	cv::Mat log_mag(size,size, CV_32FC1);
	cv::log(image_Mag, log_mag);

	//Box filter the magnitude, then take the difference
	cv::Mat log_mag_Filt(size,size, CV_32FC1);

	cv::Mat filt = cv::Mat::ones(3, 3, CV_32FC1) * 1./9.;
	//filt.convertTo(filt,-1,1.0/9.0,0);

	cv::filter2D(log_mag, log_mag_Filt, -1, filt);

	//cv::subtract(log_mag, log_mag_Filt, log_mag);
	log_mag -= log_mag_Filt;
	cv::exp(log_mag, image_Mag);

	cv::polarToCart(image_Mag, image_Phase, realInput, imaginaryInput,0);

	vec.clear();
	vec.push_back(realInput);
	vec.push_back(imaginaryInput);
	cv::merge(vec, dft_A);

	cv::dft(dft_A, dft_A, cv::DFT_INVERSE,size);

	dft_A = abs(dft_A);
	dft_A.mul(dft_A);

	cv::split(dft_A, vec);

	result_image = vec[0];
}

void DirtDetection::SaliencyDetection_C3(const cv::Mat& color_image, const cv::Mat* mask)
{
	cv::Mat fci; // "fci"<-> first channel image
	cv::Mat sci; // "sci"<-> second channel image
	cv::Mat tci; //"tci"<-> second channel image

	std::vector<cv::Mat> vec;
	vec.push_back(fci);
	vec.push_back(sci);
	vec.push_back(tci);

	cv::split(color_image,vec);

	fci = vec[0];
	sci = vec[1];
	tci = vec[2];

	cv::Mat res_fci; // "fci"<-> first channel image
	cv::Mat res_sci; // "sci"<-> second channel image
	cv::Mat res_tci; //"tci"<-> second channel image

	DirtDetection::SaliencyDetection_C1(fci, res_fci);
	DirtDetection::SaliencyDetection_C1(sci, res_sci);
	DirtDetection::SaliencyDetection_C1(tci, res_tci);

	cv::Mat realInput;

	realInput = (res_fci + res_sci + res_tci)/3;

	double minv, maxv;
	cv::Point2i minl, maxl;

	cv::Size2i ksize;
	ksize.width = 3;
	ksize.height = 3;
	cv::GaussianBlur(realInput,realInput, ksize,0); //notwendig!?
	cv::GaussianBlur(realInput,realInput, ksize,0);//notwendig!?


	//Rand entfernen
	cv::Mat resultImage;
	cv::resize(realInput,resultImage,color_image.size());
	if (mask != 0)
	{
		// maske erodiere
		cv::Mat mask_eroded = mask->clone();
		cv::dilate(*mask, mask_eroded, cv::Mat(), cv::Point(-1, -1), 2);
		cv::erode(mask_eroded, mask_eroded, cv::Mat(), cv::Point(-1, -1), 25);
		cv::Mat temp;
		resultImage.copyTo(temp, mask_eroded);
		resultImage = temp;

	}

	cv::minMaxLoc(resultImage,&minv,&maxv,&minl,&maxl);

	resultImage.convertTo(resultImage,-1, 1.0/(maxv-minv), 1.0*(minv)/(maxv-minv));


	// remove saliency at the image border
	int borderX = resultImage.cols/20;
	int borderY = resultImage.rows/20;
	if (borderX > 0 && borderY > 0)
	{
	cv::Mat smallImage_ = resultImage.colRange(borderX, resultImage.cols-1-borderX);
	cv::Mat smallImage = smallImage_.rowRange(borderY, smallImage_.rows-1-borderY);

	copyMakeBorder(smallImage, resultImage, borderY, borderY, borderX, borderX, cv::BORDER_CONSTANT, cv::Scalar(0));
	}


	cv::imshow("SaliencyDetection", resultImage);

	cv::Mat image_postproc = cv::Mat::zeros(resultImage.size(), CV_8UC1);

	cv::Mat new_color_image = color_image;

	DirtDetection::Image_Postprocessing_C1(resultImage, image_postproc, new_color_image);

//	cv::imshow("dirt image", resultImage);
	cv::imshow("image postprocessing", new_color_image);
	cv::waitKey(10);


}

void DirtDetection::Image_Postprocessing_C1(cv::Mat input_image, cv::Mat& output_image, cv::Mat& color_image)
{
	//set dirt pixel to white
	cv::Mat image_postproc = cv::Mat::zeros(input_image.size(), CV_8UC1);
	cv::threshold(input_image, image_postproc, .5, 1, cv::THRESH_BINARY);

//	std::cout << "(input_image channels) = (" << input_image.channels() << ")" << std::endl;

	//insert image into fifo
//	Image_buffer.push_back(image_postproc);

	cv::Mat CV_8UC_image;
	image_postproc.convertTo(CV_8UC_image, CV_8UC1);


//	Mat dst = Mat::zeros(img.rows, img.cols, CV_8UC3);
//	dst = color_image;

    vector<vector<Point> > contours;
    vector<Vec4i> hierarchy;

    cv::findContours(CV_8UC_image, contours, hierarchy, CV_RETR_LIST, CV_CHAIN_APPROX_SIMPLE);

    Scalar color(255, 255, 255);
    cv::RotatedRect rec;

    for (int i = 0; i < contours.size(); i++)
    {
		rec = minAreaRect(contours[i]);
    	cv::ellipse(color_image, rec, color);
    }

//    Scalar color( rand()&255, rand()&255, rand()&255 );
//    cv::drawContours( dst, contours, -1, color);



//	cv::Mat picture;

//	std::cout << "(height,width) = (" << image_postproc.size().height << ", " << image_postproc.size().width << ")" << std::endl;
//
//	for (int i = 0; i < Image_buffer.size(); i++)
//	{
//		if (i != 0)
//		{
//			picture = picture +  Image_buffer[i];
//		}
//		else
//		{
//			picture = Image_buffer[i];
//		}
//
//	}
//
//	cv::threshold(picture, output_image, 1.5, 1, cv::THRESH_BINARY);
//
//	if (Image_buffer.size() > Image_buffer_size )
//	{
//		Image_buffer.erase(Image_buffer.begin(), Image_buffer.begin()+1);
//	}

//	std::cout << "(Image buffer size) = (" << Image_buffer.size() << ")" << std::endl;

}

void DirtDetection::SaliencyDetection_C1_old_cv_code(const sensor_msgs::ImageConstPtr& color_image_msg)
{
	cv_bridge::CvImageConstPtr color_image_ptr;
	cv::Mat color_image;
	convertColorImageMessageToMat(color_image_msg, color_image_ptr, color_image);

	// color_image is now available with the current image from your camera

	cv::imshow("image", color_image);
	//cv::waitKey(10);


	//int thresh = 350;
	int scale = 6;

	//convert color image to one channel gray-scale image
	//color_image -> gray_image
    IplImage hsrc = color_image;
    IplImage *src = &hsrc;

    /* get image properties */
    int width  = src->width;
    int height = src->height;

    /* create new image for the grayscale version */
    IplImage * gray_image = cvCreateImage( cvSize( width, height ), IPL_DEPTH_8U, 1 );

    /* CV_RGB2GRAY: convert RGB image to grayscale */
    cvCvtColor( src, gray_image, CV_RGB2GRAY );


    cv::Mat bild(gray_image);

	cv::imshow("image3", bild);
	//cv::waitKey(10);


	//IplImage imageIpl = (IplImage) gray_image;
	IplImage* image = gray_image; //& imageIpl;

	//given a one channel image
	unsigned int size = (int)floor((float)pow(2.0,scale)); //the size to do the saliency at

	IplImage* bw_im = cvCreateImage(cvSize(size,size), IPL_DEPTH_8U,1);
	cvResize(image, bw_im);
	IplImage* realInput = cvCreateImage( cvGetSize(bw_im), IPL_DEPTH_32F, 1);
	IplImage* imaginaryInput = cvCreateImage( cvGetSize(bw_im), IPL_DEPTH_32F, 1);
	IplImage* complexInput = cvCreateImage( cvGetSize(bw_im), IPL_DEPTH_32F, 2);

	cvScale(bw_im, realInput, 1.0/255.0);
	cvZero(imaginaryInput);
	cvMerge(realInput, imaginaryInput, NULL, NULL, complexInput);
	CvMat* dft_A = cvCreateMat( size, size, CV_32FC2 );

	// copy A to dft_A and pad dft_A with zeros
	CvMat tmp;
	cvGetSubRect( dft_A, &tmp, cvRect(0,0, size,size));
	cvCopy( complexInput, &tmp );
	// cvZero(&tmp);

	cvDFT( dft_A, dft_A, CV_DXT_FORWARD, size );
	cvSplit( dft_A, realInput, imaginaryInput, NULL, NULL );
	// Compute the phase angle
	IplImage* image_Mag = cvCreateImage(cvSize(size, size), IPL_DEPTH_32F, 1);
	IplImage* image_Phase = cvCreateImage(cvSize(size, size), IPL_DEPTH_32F, 1);


	//compute the phase of the spectrum
	cvCartToPolar(realInput, imaginaryInput, image_Mag, image_Phase, 0);

	IplImage* log_mag = cvCreateImage(cvSize(size, size), IPL_DEPTH_32F, 1);
	cvLog(image_Mag, log_mag);

	//Box filter the magnitude, then take the difference
	IplImage* log_mag_Filt = cvCreateImage(cvSize(size, size), IPL_DEPTH_32F, 1);
	CvMat* filt = cvCreateMat(3,3, CV_32FC1);
	cvSet(filt,cvScalarAll(1.0/9.0));
	cvFilter2D(log_mag, log_mag_Filt, filt);
	cvReleaseMat(&filt);

	cvSub(log_mag, log_mag_Filt, log_mag);

	cvExp(log_mag, image_Mag);

	cvPolarToCart(image_Mag, image_Phase, realInput, imaginaryInput,0);
	//cvExp(log_mag, image_Mag);

	cvMerge(realInput, imaginaryInput, NULL, NULL, dft_A);
	cvDFT( dft_A, dft_A, CV_DXT_INV_SCALE, size);

	cvAbs(dft_A, dft_A);
	cvMul(dft_A,dft_A, dft_A);
	cvGetSubRect( dft_A, &tmp, cvRect(0,0, size,size));
	cvCopy( &tmp, complexInput);
	cvSplit(complexInput, realInput, imaginaryInput, NULL,NULL);

	IplImage* result_image = cvCreateImage(cvGetSize(image),IPL_DEPTH_32F, 1);
	double minv, maxv;
	CvPoint minl, maxl;
	cvSmooth(realInput,realInput);
	cvSmooth(realInput,realInput);
	cvMinMaxLoc(realInput,&minv,&maxv,&minl,&maxl);
	//printf("Max value %lf, min %lf\n", maxv,minv);
	maxv= 0.03;
	cvScale(realInput, realInput, 1.0/(maxv-minv), 1.0*(minv)/(maxv-minv));
	cvResize(realInput, result_image);


	cv::Mat resultImage(result_image);


	// remove saliency at the image border
	int borderX = resultImage.cols/20;
	int borderY = resultImage.rows/20;
	if (borderX > 0 && borderY > 0)
	{
	cv::Mat smallImage_ = resultImage.colRange(borderX, resultImage.cols-1-borderX);
	cv::Mat smallImage = smallImage_.rowRange(borderY, smallImage_.rows-1-borderY);

	copyMakeBorder(smallImage, resultImage, borderY, borderY, borderX, borderX, cv::BORDER_CONSTANT, cv::Scalar(0));
	}

	//CvMat -> cv::Mat
	//cv::meanStdDev();

	//cv::Mat stainImage;
	// check if the image makes sense (or convert to 0...255)
	//resultImage.convertTo(stainImage, -1, 1.0, 0.0);


	//mThresholdHou = thresh/100.0*cvAvg(realInput).val[0];

	cv::imshow("image2", resultImage);
	cv::waitKey(10);


	//stainImage.release();

	resultImage.release();
	cvReleaseImage(&result_image);
	cvReleaseImage(&realInput);
	cvReleaseImage(&imaginaryInput);
	cvReleaseImage(&complexInput);
	cvReleaseMat(&dft_A);
	cvReleaseImage(&bw_im);

	cvReleaseImage(&image_Mag);
	cvReleaseImage(&image_Phase);

	cvReleaseImage(&log_mag);
	cvReleaseImage(&log_mag_Filt);
	cvReleaseImage(&bw_im);

}
