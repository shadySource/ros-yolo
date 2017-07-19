#!/usr/bin/env python
# YOLO ros object, uses the subscriber to evaluate images
from __future__ import print_function

import os
import sys
import rospy
import cv2
import tensorflow as tf
import numpy as np
from keras.layers import Input
from keras.models import model_from_json
from keras import backend as K
import argparse

import context

from yad2k.utils.draw_boxes import draw_boxes
from retrain_yolo import create_model
from yad2k.models.keras_yolo import yolo_head_np, yolo_eval
from subscriber import videosub


class yolo(object):
    '''
    YOLOv2 class integrated with YAD2K and ROS
    '''
    def __init__(self, json_path, anchors_path, classes_path, weights_path, score_threshold=0.3, iou_threshold=0.6, max_detections=15):  
        # Load classes and anchors.
        with open(classes_path) as f:
                self.class_names = f.readlines()
        self.class_names = [c.strip() for c in self.class_names]

        with open(anchors_path) as f:
            self.anchors = f.readline()
            self.anchors = [float(x) for x in self.anchors.split(',')]
            self.anchors = np.array(self.anchors).reshape(-1, 2)

        self.image_input = Input(shape=(None, None, 3))

        yolo_json_file = open(json_path, 'r')
        yolo_json = yolo_json_file.read()
        yolo_json_file.close()

        self.yolo_model, garbage = create_model(self.anchors, self.class_names, False, 0)
        
        self.yolo_model.load_weights(weights_path)

        self.yolo_model.summary()

        self.max_boxes=max_detections,
        self.score_threshold=score_threshold,
        self.iou_threshold=iou_threshold

        print('yolo object created')

    def pred(self, image_s, display_shape=(640, 480)):
        # Make predictions for images in (num_images, height, width, channel) format
        assert len(image_s.shape) == 4 # image must have 4 dims ready to be sent into the graph
        # TODO allow multiple images at once.
        assert image_s.shape[0] == 1
        features = self.yolo_model.predict(image_s)

        proc = yolo_head_np(features, self.anchors, len(self.class_names))

        out_boxes, out_scores, out_classes = yolo_eval(proc, (640, 480), max_boxes=self.max_boxes,
            score_threshold=self.score_threshold, iou_threshold=self.iou_threshold)

        return out_boxes, out_scores, out_classes

    def display(self, out_boxes, out_scores, out_classes, image, name):
        if len(out_boxes) == 0:
            cv2.imshow(name, image)
        else:
            image = draw_boxes(image, out_boxes, out_classes, self.class_names, scores=out_scores, rectify=False)
            cv2.imshow(name, image)
        cv2.waitKey(10)

def _main(args):
    anchors_path= os.path.expanduser(args.anchors_path)
    classes_path= os.path.expanduser(args.classes_path)
    weights_path = os.path.expanduser(args.weights_path)
    json_path = os.path.expanduser(args.json_path)

    rospy.init_node("yoloNode")

    yo = yolo(json_path, anchors_path, classes_path, weights_path, .4, .4, 100)

    vid1 = videosub(args.first_topic)
    if args.second_topic is not None:
        vid2 = videosub(args.second_topic)

    rate = rospy.Rate(15)
    image = None
    while not rospy.is_shutdown():
        # Grab new images from the subscribers
        if vid1.newImgAvailable:
            image, image_data = vid1.getProcessedImage()
            boxes, scores, classes = yo.pred(image_data)
            yo.display(boxes, scores, classes, image, vid1.topic) # Display
        if args.second_topic is not None and vid2.newImgAvailable:
            image, image_data = vid2.getProcessedImage()
            boxes, scores, classes = yo.pred(image_data)
            yo.display(boxes, scores, classes, image, vid2.topic)

        rate.sleep()

if __name__ == '__main__':
    # Configure default paths
    filepath = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.abspath(os.path.join(filepath, '..', '..', 'YAD2K'))
    
    # Args
    argparser = argparse.ArgumentParser(
        description="launch a yolo model, subscribed to topic '/sensors/camera0/jpegbuffer'")

    argparser.add_argument(
        '-f',
        '--first_topic',
        help="(optional)First topic to subscribe to. defaults to '/sensors/camera0/jpegbuffer'",
        default='/sensors/camera0/jpegbuffer')

    argparser.add_argument(
        '-s',
        '--second_topic',
        help='(optional) Second topic to subscribe to. Leave blank if None.',
        default=None)

    argparser.add_argument(
        '-c',
        '--classes_path',
        help='(optional)path to classes file, defaults to YAD2K/model_data/aerial_classe.txt',
        default=os.path.join(filepath, 'model_data', 'aerial_classes.txt'))

    argparser.add_argument(
        '-a',
        '--anchors_path',
        help='(optional)path to anchors file, defaults to YAD2K/model_data/yolo_anchors.txt',
        default=os.path.join(filepath, 'model_data', 'yolo_anchors.txt'))
    
    argparser.add_argument(
        '-w',
        '--weights_path',
        help='(optional) path to model weights file, defaults to YAD2K/trained_stage_2_best.h5',
        default=os.path.join(filepath, 'trained_stage_2_best.h5'))

    argparser.add_argument(
        '-j',
        '--json_path',
        help='(optional) path to model json file, defaults to YAD2K/model_data/yolo.json',
        default=os.path.join(filepath, 'model_data', 'yolo.json'))

    args = argparser.parse_args()

    _main(args)
