import sys
import numpy as np
import pyzed.sl as sl
import cv2
import math
from utils.yolo_classes import get_cls_dict
from utils.visualization import BBoxVisualization
from utils.yolo_with_plugins import TrtYOLO
import os
#import pycuda.autoinit
import time
def main() :

    # Create a ZED camera object
    zed = sl.Camera()

    # Set configuration parameters
    input_type = sl.InputType()
    if len(sys.argv) >= 2 :
        input_type.set_from_svo_file(sys.argv[1])
    init = sl.InitParameters(input_t=input_type)
    init.camera_resolution = sl.RESOLUTION.HD1080
    init.depth_mode = sl.DEPTH_MODE.PERFORMANCE
    init.coordinate_units = sl.UNIT.MILLIMETER

    # Open the camera
    err = zed.open(init)
    if err != sl.ERROR_CODE.SUCCESS :
        print(repr(err))
        zed.close()
        exit(1)

  
    # Set runtime parameters after opening the camera
    runtime = sl.RuntimeParameters()
    runtime.sensing_mode = sl.SENSING_MODE.STANDARD

    # Prepare new image size to retrieve half-resolution images
    image_size = zed.get_camera_information().camera_resolution
    #image_size.width = image_size.width /2
    #image_size.height = image_size.height /2

    # Declare your sl.Mat matrices
    image_zed = sl.Mat(image_size.width, image_size.height, sl.MAT_TYPE.U8_C4)
    depth_image_zed = sl.Mat(image_size.width, image_size.height, sl.MAT_TYPE.U8_C4)
    point_cloud = sl.Mat()
    
    
    #=========== Yolov4 TensorRt ağırlıkları yüklenmektedir =======================
    
    category_num = 17
    model_trt = 'yolov4'
    letter_box = False
    if category_num <= 0:
        raise SystemExit('ERROR: bad category_num (%d)!' % category_num)
    if not os.path.isfile('yolo/{}.trt'.format(model_trt)):
        raise SystemExit('ERROR: file (yolo/{}.trt) not found!'.format(model_trt))
    
    cls_dict = get_cls_dict(category_num)
    vis = BBoxVisualization(cls_dict)
    trt_yolov4 = TrtYOLO(model_trt, category_num, letter_box)
    
    def YOLOv4_video(pred_image):
        image_test = cv2.cvtColor(pred_image, cv2.COLOR_RGBA2RGB)
        image = image_test.copy()
        boxes, confs, clss = trt_yolov4.detect(image, conf_th=0.3)
        return clss,confs,boxes
        
        
    key = ' '
    LABELS = [ 'girilmez',
                'tasit_trafigine_kapali',
                'duz_veya_sola',
                'duz_veya_saga',
                'yalnizca_sola',
                '20_hiz_limiti_sonu',
                '30_limit',
                '20_limit',
                'yalnizca_saga',
                'saga_donulmez',
                'sola_donulmez',
                'dur',
                'park_yapilmaz',
                'park',
                'durak',
                'kirmizi_isk',
                'sari_isik',
                'yesil_isik']

    COLORS = [[0, 0, 255]]
    prev_frame_time=0
    new_frame_time=0
    while key != 113 :
        err = zed.grab(runtime)
        if err == sl.ERROR_CODE.SUCCESS :
            # Retrieve the left image, depth image in the half-resolution
            zed.retrieve_image(image_zed, sl.VIEW.LEFT, sl.MEM.CPU, image_size)
            zed.retrieve_image(depth_image_zed, sl.VIEW.DEPTH, sl.MEM.CPU, image_size)
            # Retrieve the RGBA point cloud in half resolution
            zed.retrieve_measure(point_cloud, sl.MEASURE.XYZRGBA, sl.MEM.CPU, image_size)
            
            # Get and print distance value in mm at the center of the image
            # We measure the distance camera - object using Euclidean distance
            
            # To recover data from sl.Mat to use it with opencv, use the get_data() method
            # It returns a numpy array that can be used as a matrix with opencv
            image_ocv = image_zed.get_data()
            #depth_image_ocv = depth_image_zed.get_data()
            classes,confidences,boxes = YOLOv4_video(image_ocv)
            
            for cl,score,(x_min,y_min,x_max,y_max) in zip(classes,confidences,boxes):
                start_pooint = (int(x_min),int(y_min))
                end_point = (int(x_max),int(y_max))
                
                x = int(x_min +( x_max-x_min)/2)
                y = int(y_min + (y_max-y_min)/2)
                color = COLORS[0]
                img =cv2.rectangle(image_ocv,start_pooint,end_point,color,3)
                img = cv2.circle(img,(x,y),5,[0,0,255],5)
                text = f'{LABELS[int(cl)]}: {score:0.2f}'
                cv2.putText(img,text,(int(x_min),int(y_min-7)),cv2.FONT_ITALIC,1,COLORS[0],2 )
                
                x = round(x)
                y = round(y)
                err, point_cloud_value = point_cloud.get_value(x, y)
                distance = math.sqrt(point_cloud_value[0] * point_cloud_value[0] +
                                    point_cloud_value[1] * point_cloud_value[1] +
                                    point_cloud_value[2] * point_cloud_value[2])
                print("Distance to Camera at (class : {0}, score : {1:0.2f}): distance : {2:0.2f} mm".format(LABELS[int(cl)], score, distance), end="\r")
                cv2.putText(img,"Distance: "+str(round(distance/1000,2))+'m',(int(x_max-180),int(y_max+30)),cv2.FONT_HERSHEY_COMPLEX,1,(0,255,0),1)
                
                new_frame_time=time.time()
                fps = 1/(new_frame_time-prev_frame_time)
                prev_frame_time = new_frame_time
                
                print('FPS : %.2f  ' % fps)
                cv2.imshow("Image", img)
                    
            
            #cv2.imshow("Image", image_ocv)
            #cv2.imshow("Depth", depth_image_ocv)
            
            key = cv2.waitKey(1)


    cv2.destroyAllWindows()
    zed.close()

    print("\nFINISH")

if __name__ == "__main__":
    main()