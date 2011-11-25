/*
 * dirt_detection.h
 *
 *  Created on: 06.10.2011
 *      Author: rmb-hs
 */

#ifndef DIRT_DETECTION_H_
#define DIRT_DETECTION_H_

//##################
//#### includes ####

// standard includes
#include <iostream>
#include <string>

// ROS includes
#include <ros/ros.h>

// ROS message includes
#include <sensor_msgs/Image.h>
#include <sensor_msgs/PointCloud2.h>

// topics
#include <image_transport/image_transport.h>
#include <image_transport/subscriber_filter.h>

// opencv
#include <opencv/cv.h>
#include <opencv/highgui.h>
#include <cv_bridge/cv_bridge.h>
#include <sensor_msgs/image_encodings.h>

// PCL
#include <pcl/ros/conversions.h>
#include <pcl/point_cloud.h>
#include <pcl/point_types.h>

#include <pcl/sample_consensus/method_types.h>
#include <pcl/sample_consensus/model_types.h>
#include <pcl/segmentation/sac_segmentation.h>
#include <pcl/filters/extract_indices.h>

#include <pcl/io/pcd_io.h>

//bridge
#include <cv_bridge/cv_bridge.h>
//#include <cv_bridge/CvBridge.h>

namespace ipa_DirtDetection {

//####################
//#### node class ####
class DirtDetection
{
protected:
	image_transport::ImageTransport* it_;
	image_transport::Subscriber color_camera_image_sub_; ///< Color camera image topic
	ros::Subscriber camera_depth_points_sub_;


	ros::NodeHandle node_handle_; ///< ROS node handle

	struct bgr
	{
		uchar b;
		uchar g;
		uchar r;
	};


public:

	//Constructor
	DirtDetection(ros::NodeHandle node_handle);

	//Destructor
	~DirtDetection();

	//create subscribers
	void init();


	//callback functions
	void imageDisplayCallback(const sensor_msgs::ImageConstPtr& color_image_msg);
	void planeDetectionCallback(const sensor_msgs::PointCloud2ConstPtr& point_cloud2_rgb_msg);

	//convert functions
	unsigned long convertColorImageMessageToMat(const sensor_msgs::Image::ConstPtr& color_image_msg, cv_bridge::CvImageConstPtr& color_image_ptr, cv::Mat& color_image);
	void convertPointCloudMessageToPointCloudPcl(const sensor_msgs::PointCloud2ConstPtr& point_cloud2_rgb_msg, pcl::PointCloud<pcl::PointXYZRGB>::Ptr &point_cloud_XYZRGB);


	//functions
	void planeDetection(pcl::PointCloud<pcl::PointXYZRGB>::Ptr input_cloud);

	void SaliencyDetection_C1(cv::Mat& one_channel_image, cv::Mat& result_image);
	void SaliencyDetection_C3(const cv::Mat& color_image, const cv::Mat* mask = 0);
	void SaliencyDetection_C1_old_cv_code(const sensor_msgs::ImageConstPtr& color_image_msg);

};

};


#endif /* DIRT_DETECTION_H_ */
