# Licensed under the Apache License, Version 2.0 (the "License"); you may not use
# this file except in compliance with the License. You may obtain a copy of the
# License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed
# under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
# CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.

import os.path
import cv2
import numpy as np

import rclpy

from sensor_msgs.msg import CameraInfo
from geometry_msgs.msg import Point
from duckietown_msgs.msg import (Pixel, Vector2D)

from image_geometry import PinholeCameraModel

#from duckietown_utils.path_utils import get_ros_package_path
#from duckietown_utils.yaml_wrap import (yaml_load_file, yaml_write_to_file)

#from duckietown_utils import (logger, get_duckiefleet_root)

class GroundProjection():

    def __init__(self, robot_name="birdbot0"):

        # defaults overwritten by param
        self.robot_name = robot_name
        self.rectified_input = False

        # Load homography
        self.H = self.load_homography()
        self.Hinv = np.linalg.inv(self.H)

        self.pcm_ = PinholeCameraModel()

        # Load checkerboard information
        #self.board_ = self.load_board_info()

    # wait until we have received the camera info message through ROS and then initialize
    def initialize_pinhole_camera_model(self,camera_info):
        self.ci_=camera_info
        self.pcm_.fromCameraInfo(camera_info)
        print("pinhole camera model initialized")

    def vector2pixel(self, vec):
        pixel = Pixel()
        cw = self.ci_.width
        ch = self.ci_.height
        pixel.u = int(cw * vec.x)
        pixel.v = int(ch * vec.y)
        if (pixel.u < 0): pixel.u = 0
        if (pixel.u > cw -1): pixel.u = cw - 1
        if (pixel.v < 0): pixel.v = 0
        if (pixel.v > ch - 1): pixel.v = 0
        return pixel

    def pixel2vector(self, pixel):
        vec = Vector2D()
        vec.x = pixel.u / self.ci_.width
        vec.y = pixel.v / self.ci_.height
        return vec

    def vector2ground(self, vec):
        pixel = self.vector2pixel(vec)
        return self.pixel2ground(pixel)

    def ground2vector(self, point):
        pixel = self.ground2pixel(point)
        return self.pixel2vector(pixel)

    def pixel2ground(self,pixel):
        uv_raw = np.array([pixel.u, pixel.v])
        if not self.rectified_input:
            uv_raw = self.pcm_.rectifyPoint(uv_raw)
        #uv_raw = [uv_raw, 1]
        uv_raw = np.append(uv_raw, np.array([1]))
        ground_point = np.dot(self.H, uv_raw)
        point = Point()
        x = ground_point[0]
        y = ground_point[1]
        z = ground_point[2]
        point.x = x/z
        point.y = y/z
        point.z = 0.0
        return point

    def ground2pixel(self, point):
        ground_point = np.array([point.x, point.y, 1.0])
        image_point = np.dot(self.Hinv, ground_point)
        image_point = image_point / image_point[2]


        pixel = Pixel()
        if not self.rectified_input:
            distorted_pixel = self.pcm_.project3dToPixel(image_point)
            pixel.u = distorted_pixel[0]
            pixel.v = distorted_pixel[1]
        else:
            pixel.u = image_point[0]
            pixel.v = image_point[1]

    def rectify(self, cv_image_raw):
        '''Undistort image'''
        cv_image_rectified = np.zeros(np.shape(cv_image_raw))
        mapx = np.ndarray(shape=(self.pcm_.height, self.pcm_.width, 1), dtype='float32')
        mapy = np.ndarray(shape=(self.pcm_.height, self.pcm_.width, 1), dtype='float32')
        mapx, mapy = cv2.initUndistortRectifyMap(self.pcm_.K, self.pcm_.D, self.pcm_.R, self.pcm_.P, (self.pcm_.width, self.pcm_.height), cv2.CV_32FC1, mapx, mapy)
        return cv2.remap(cv_image_raw, mapx, mapy, cv2.INTER_CUBIC, cv_image_rectified)

    def load_homography(self):
        '''Load homography (extrinsic parameters)'''
        """
        filename = (get_duckiefleet_root() + "/calibrations/camera_extrinsic/" + self.robot_name + ".yaml")
        if not os.path.isfile(filename):
            #logger.warn("no extrinsic calibration parameters for {}, trying default".format(self.robot_name))
            filename = (get_duckiefleet_root() + "/calibrations/camera_extrinsic/default.yaml")
            if not os.path.isfile(filename):
                #logger.error("can't find default either, something's wrong")
            else:
                data = yaml_load_file(filename)
        else:
            #rospy.loginfo("Using extrinsic calibration of " + self.robot_name)
            data = yaml_load_file(filename)
        #logger.info("Loaded homography for {}".format(os.path.basename(filename)))
        return np.array(data['homography']).reshape((3,3))
        """

        # hardcorded birdbot0 homography
        #return np.array([[-1.3138222289537473e-05,-0.00016799247320246641, -0.18508764249409215],
        #                 [0.0008702503150508597, -1.314730233433855e-06, -0.2779744199471874],
        #                 [-7.940529271577331e-05,-0.006045110837995103,1.0]])
        return np.array([[-5.987554218305854e-05,-0.00012542467699075597, -0.183339048091576],
                    [0.0008439191581241052, -3.098547600170272e-05, -0.28159137198032724],
                    [-0.00015406069103711482,-0.006343978853492832, 0.9999999999999999]])


"""
def yaml_load_file(filename):
    import yaml
    try:
        f = open(filename, 'r')
    except IOError as err:
        print("Could not open file, IO Error({0})".format(err))
        return
    data = yaml.safe_load(f)
    return data
"""

"""
    def estimate_homography(self,cv_image):
        '''Estimate ground projection using instrinsic camera calibration parameters'''
        cv_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        cv_image_rectified = self.rectify(cv_image)
        logger.info("image rectified")

        ret, corners = cv2.findChessboardCorners(cv_image_rectified, (self.board_['width'], self.board_['height']))
        if ret == False:
            logger.error("No corners found in image")
            exit(1)
        if len(corners) != self.board_['width'] * self.board_['height']:
            logger.error("Not all corners found in image")
            exit(2)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.01)
        corners2 = cv2.cornerSubPix(cv_image_rectified, corners, (11,11), (-1,-1), criteria)

        #TODO flip checks
        src_pts = []
        for r in range(self.board_['height']):
            for c in range(self.board_['width']):
                src_pts.append(np.array([r * self.board_['square_size'] , c * self.board_['square_size']] , dtype='float32') + self.board_['offset'])
        # OpenCV labels corners left-to-right, top-to-bottom
        # We're having a problem with our pattern since it's not rotation-invariant

        # only reverse order if first point is at bottom right corner
        if ((corners[0])[0][0] < (corners[self.board_['width']*self.board_['height']-1])[0][0] and (corners[0])[0][0] < (corners[self.board_['width']*self.board_['height']-1])[0][1]):
            rospy.loginfo("Reversing order of points.")
            src_pts.reverse()


        # Compute homography from image to ground
        self.H, mask = cv2.findHomography(corners2.reshape(len(corners2), 2), np.array(src_pts), cv2.RANSAC)
        extrinsics_filename = get_duckiefleet_root() + "/calibrations/camera_extrinsic/" + self.robot_name + ".yaml"
        self.write_homography(extrinsics_filename)
        logger.info("Wrote ground projection to {}".format(extrinsics_filename))

        # Check if specific point in matrix is larger than zero (this would definitly mean we're having a corrupted rotation matrix)
        if(self.H[1][2] > 0):
            rospy.logerr("WARNING: Homography could be corrupt!")

    def load_homography(self):
        '''Load homography (extrinsic parameters)'''
        filename = (get_duckiefleet_root() + "/calibrations/camera_extrinsic/" + self.robot_name + ".yaml")
        if not os.path.isfile(filename):
            logger.warn("no extrinsic calibration parameters for {}, trying default".format(self.robot_name))
            filename = (get_duckiefleet_root() + "/calibrations/camera_extrinsic/default.yaml")
            if not os.path.isfile(filename):
                logger.error("can't find default either, something's wrong")
            else:
                data = yaml_load_file(filename)
        else:
            rospy.loginfo("Using extrinsic calibration of " + self.robot_name)
            data = yaml_load_file(filename)
        logger.info("Loaded homography for {}".format(os.path.basename(filename)))
        return np.array(data['homography']).reshape((3,3))

    def write_homography(self, filename):
        ob = {'homography': sum(self.H.reshape(9,1).tolist(),[])}
        print ob
        yaml_write_to_file(ob,filename)



    def load_board_info(self, filename=''):
        '''Load calibration checkerboard info'''
        if not os.path.isfile(filename):
            filename = get_ros_package_path('duckietown') + '/config/baseline/ground_projection/ground_projection/default.yaml'
        target_data = yaml_load_file(filename)
        target_info = {
            'width': target_data['board_w'],
            'height': target_data['board_h'],
            'square_size': target_data['square_size'],
            'x_offset': target_data['x_offset'],
            'y_offset': target_data['y_offset'],
            'offset': np.array([target_data['x_offset'], -target_data['y_offset']]),
            'size': (target_data['board_w'], target_data['board_h']),
          }
        logger.info("Loaded checkerboard parameters")
        return target_info
"""
