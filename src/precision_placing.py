#!/usr/bin/env python
import sys
import math
import rospy
import copy
import tf
import numpy
import moveit_commander 
import moveit_msgs.msg
import std_msgs.msg 
import geometry_msgs.msg 
import roslib; roslib.load_manifest('robotiq_c_model_control'); roslib.load_manifest('visualization_marker_tutorials')
from robotiq_c_model_control.msg import _CModel_robot_output as outputMsg
from robotiq_c_model_control.msg import _CModel_robot_input  as inputMsg
from apriltags_ros.msg import * 
from geometry_msgs.msg import WrenchStamped
from std_msgs.msg import *
from rospy import init_node, is_shutdown
from dynamixel_msgs.msg import JointState
from dynamixel_controllers.srv import *
from visualization_msgs.msg import Marker
from visualization_msgs.msg import MarkerArray

##___GLOBAL VARIABLES___###
velocity = 0.3 #velocity scaling factor (0, 1.0] - Safe value for a real robot is ~0.05
#Dynamixel
goal_pos = float;
goal_speed = 1.0;

##___INITIALIZATION___###
moveit_commander.roscpp_initialize(sys.argv) #initialize the moveit commander
rospy.init_node('move_group_python_interface_tutorial', anonymous=True) #initialize rospy 
robot = moveit_commander.RobotCommander() #Instantiate a RobotCommander object
scene = moveit_commander.PlanningSceneInterface() #Instantiate a Planning SceneInterface Object
group = moveit_commander.MoveGroupCommander("manipulator") #Instantiate a MoveGroupCommander object. This object is an interface to one group of joints. 
display_trajectory_publisher = rospy.Publisher('/move_group/display_planned_path', moveit_msgs.msg.DisplayTrajectory) #Create DisplayTrajectory publisher which is used to publish trajectories (RVIZ visual)

##__Publishers&Listeners__##
pub = rospy.Publisher('CModelRobotOutput', outputMsg.CModel_robot_output)
regrasp_pub = rospy.Publisher('regrasp_status', String, queue_size = 10)
psi_pub = rospy.Publisher('psi_current', Float32, queue_size = 10)
length_pub = rospy.Publisher('length_value', Float32, queue_size = 10)
tf_listener = tf.TransformListener()
tf_broadcaster = tf.TransformBroadcaster()
dynamixel_pub = rospy.Publisher('tilt_controller/command', Float64, queue_size=10)
marker_pub = rospy.Publisher('visualization_marker_array', MarkerArray)




#############################################################################################################################################################################################################
####____MARKER____####
#############################################################################################################################################################################################################
def waypoints_marker(waypoints, color='red', assign_id = 0):
    markerArray = MarkerArray()

    count = 0
    MARKERS_MAX = 10000

    for i in range(len(waypoints)):
        
        waypoint_position = [waypoints[i].position.x, waypoints[i].position.y, waypoints[i].position.z, 1] 
        waypoint_orientation = [waypoints[i].orientation.x, waypoints[i].orientation.y, waypoints[i].orientation.z, waypoints[i].orientation.w]  
                
        marker = Marker()
        marker.header.frame_id = "/world"
        marker.type = marker.ARROW
        marker.action = marker.ADD
        marker.scale.x = 0.05
        marker.scale.y = 0.001
        marker.scale.z = 0.001
        if color is 'red':
            marker.color.a = 1.0
            marker.color.r = 1.0
            marker.color.g = 0.0
            marker.color.b = 0.0
        elif color is 'green':
            marker.color.a = 1.0
            marker.color.r = 0.0
            marker.color.g = 1.0
            marker.color.b = 0.0
        elif color is 'blue':
            marker.color.a = 1.0
            marker.color.r = 0.0
            marker.color.g = 0.0
            marker.color.b = 1.0
 	elif color is 'yellow':
            marker.color.a = 1.0
            marker.color.r = 1.0
            marker.color.g = 1.0
            marker.color.b = 0.0
	marker.pose.orientation.x = waypoint_orientation[0]
	marker.pose.orientation.y = waypoint_orientation[1]
	marker.pose.orientation.z = waypoint_orientation[2]
        marker.pose.orientation.w = waypoint_orientation[3]
        marker.pose.position.x = waypoint_position[0]
        marker.pose.position.y = waypoint_position[1] 
        marker.pose.position.z = waypoint_position[2] 

        # We add the new marker to the MarkerArray, removing the oldest
        # marker from it when necessary
        if(count > MARKERS_MAX):
            markerArray.markers.pop(0)

        markerArray.markers.append(marker)

        # Renumber the marker IDs
        id = assign_id
        for m in markerArray.markers:
            m.id = id
            id += 1

        # Publish the MarkerArray
        marker_pub.publish(markerArray)
        count += 1

        #rospy.sleep(0.01)

def reference_marker(position, color='red', assign_id = 0):
    markerArray = MarkerArray()
    count = 0
    MARKERS_MAX = 10000
    marker = Marker()
    marker.header.frame_id = "/world"
    marker.type = marker.SPHERE
    marker.action = marker.ADD
    marker.scale.x = 0.02
    marker.scale.y = 0.02
    marker.scale.z = 0.02
    if color is 'red':
        marker.color.a = 1.0
        marker.color.r = 1.0
        marker.color.g = 0.0
        marker.color.b = 0.0
    elif color is 'green':
        marker.color.a = 1.0
        marker.color.r = 0.0
        marker.color.g = 1.0
        marker.color.b = 0.0
    elif color is 'blue':
        marker.color.a = 1.0
        marker.color.r = 0.0
        marker.color.g = 0.0
        marker.color.b = 1.0
    elif color is 'yellow':
        marker.color.a = 1.0
        marker.color.r = 1.0
        marker.color.g = 1.0
        marker.color.b = 0.0
    marker.pose.orientation.w = 1.0
    marker.pose.position.x = position[0]
    marker.pose.position.y = position[1] 
    marker.pose.position.z = position[2] 

    # We add the new marker to the MarkerArray, removing the oldest
    # marker from it when necessary
    if(count > MARKERS_MAX):
        markerArray.markers.pop(0)
    markerArray.markers.append(marker)
    # Renumber the marker IDs
    id = assign_id
    for m in markerArray.markers:
        m.id = id
        id += 1

    # Publish the MarkerArray
    marker_pub.publish(markerArray)
    count += 1

#############################################################################################################################################################################################################
####____GRIPPER CONTROL____####
#############################################################################################################################################################################################################
###___Activate gripper___###
def gactive(pub):
  command = outputMsg.CModel_robot_output();
  command.rACT = 1
  command.rGTO = 1
  command.rSP  = 50
  command.rFR  = 150						##force need to be adjusted later
  pub.publish(command)
  rospy.sleep(0.5)
  return command

###___Reset gripper___###
def greset(pub):
  command = outputMsg.CModel_robot_output();
  command.rACT = 0
  pub.publish(command)
  rospy.sleep(0.5)

###___Set position of gripper___###
def gposition(pub,command, position):   ##0=open, 255=close
  #rospy.sleep(0.5)
  command = outputMsg.CModel_robot_output();
  command.rACT = 1
  command.rGTO = 1
  command.rSP  = 50
  command.rFR  = 150						##force need to be adjusted later
  command.rPR = position
  pub.publish(command)
  #rospy.sleep(0.5)
  return command


###___Pick-up Object___###
## This function manipulates gripper and grabs object
## distance is the distance to dive before gripping and velocity is the speed of the motion. It rises 10cm after grabbing object
def pickup(command, distance, vel):
    rospy.sleep(0.5)
    gposition(pub, command, 150) #increment gripper width
    rospy.sleep(1)
    

    resolution = 0.05 #resolution is interpreted as 1/resolution = number of interpolated points in the path
    pose_target = group.get_current_pose().pose
    x_1 = pose_target.position.x
    y_1 = pose_target.position.y
    z_1 = pose_target.position.z
    x_2 = x_1
    y_2 = y_1
    z_2 = z_1 + distance
    direction_vector = [x_2-x_1, y_2-y_1, z_2-z_1]
    pose_target = group.get_current_pose().pose #create a pose variable. The parameters can be seen from "$ rosmsg show Pose"
    waypoints = []
    waypoints.append(pose_target)
    t = 0 # counter/increasing variabe for the parametric equation of straight line      
    while t <= 1.01:
        pose_target.position.x = x_1 + direction_vector[0]*t
        pose_target.position.y = y_1 + direction_vector[1]*t
        pose_target.position.z = z_1 + direction_vector[2]*t
        t += resolution 
        
        waypoints.append(copy.deepcopy(pose_target))
         
    del waypoints[:1]
    
    plan_execute_waypoints(waypoints)

    command = outputMsg.CModel_robot_output();
    command.rACT = 1
    command.rGTO = 1
    command.rSP  = 20
    command.rFR  = 150						##force need to be adjusted later
    command.rPR = 220
    pub.publish(command)
    rospy.sleep(1)

    
    pose_target = group.get_current_pose().pose
    x_1 = pose_target.position.x
    y_1 = pose_target.position.y
    z_1 = pose_target.position.z
   
    x_2 = x_1
    y_2 = y_1
    z_2 = z_1 + 0.1
    direction_vector = [x_2-x_1, y_2-y_1, z_2-z_1]
    pose_target = group.get_current_pose().pose #create a pose variable. The parameters can be seen from "$ rosmsg show Pose"
    waypoints = []
    waypoints.append(pose_target)
    t = 0 # counter/increasing variabe for the parametric equation of straight line      
    while t <= 1.01:
        pose_target.position.x = x_1 + direction_vector[0]*t
        pose_target.position.y = y_1 + direction_vector[1]*t
        pose_target.position.z = z_1 + direction_vector[2]*t
        t += resolution 
        
        waypoints.append(copy.deepcopy(pose_target))
         
    del waypoints[:1]
    
    plan_execute_waypoints(waypoints)



#############################################################################################################################################################################################################
####____SENSING____####
#############################################################################################################################################################################################################


###___FORCE SEEK___###
def force_seek(axis_world, distance, force_direction, sensitivity, final_offset, vel):
    resolution = 0.05 #resolution is interpreted as 1/resolution = number of interpolated points in the path
    pose_target = group.get_current_pose().pose
    x_1 = pose_target.position.x
    y_1 = pose_target.position.y
    z_1 = pose_target.position.z
    if axis_world is 'x':
        x_2 = x_1 + distance
        y_2 = y_1
        z_2 = z_1
    if axis_world is 'y':
        x_2 = x_1
        y_2 = y_1 + distance
        z_2 = z_1
    if axis_world is 'z':
        x_2 = x_1
        y_2 = y_1
        z_2 = z_1 + distance
    direction_vector = [x_2-x_1, y_2-y_1, z_2-z_1]
    pose_target = group.get_current_pose().pose #create a pose variable. The parameters can be seen from "$ rosmsg show Pose"
    waypoints = []
    waypoints.append(pose_target)
    t = 0 # counter/increasing variabe for the parametric equation of straight line      
    while t <= 1.01:
        pose_target.position.x = x_1 + direction_vector[0]*t
        pose_target.position.y = y_1 + direction_vector[1]*t
        pose_target.position.z = z_1 + direction_vector[2]*t
        t += resolution 
        
        waypoints.append(copy.deepcopy(pose_target))
         
    del waypoints[:1]
    
    forceseek_asyncExecute_waypoints(waypoints)

    rospy.sleep(0.5)
    wrench = rospy.wait_for_message('/robotiq_force_torque_wrench', WrenchStamped, timeout = None)
    
    if force_direction is 'x':
        force_initial = wrench.wrench.force.x
    if force_direction is 'y':
        force_initial = wrench.wrench.force.y
    if force_direction is 'z':
        force_initial = wrench.wrench.force.z
    
    print sensitivity
    force = 0
    i = 0
    while i is not 4:
        wrench = rospy.wait_for_message('/robotiq_force_torque_wrench', WrenchStamped, timeout = None)        
        if force_direction is 'z':
            force = wrench.wrench.force.z
        if force_direction is 'y':
            force = wrench.wrench.force.y
        if force_direction is 'x':
            force = wrench.wrench.force.x 
 	if force_initial-force > sensitivity:
        #if math.fabs(force) > math.fabs(force_initial)+sensitivity:
            i += 1
        print force_initial-force
    print 'STOP'  
    group.stop()
    
    tf_listener.waitForTransform('/world', '/ee_link', rospy.Time(), rospy.Duration(4.0))
    (trans_eelink, rot_eelink) = tf_listener.lookupTransform('/world', '/ee_link', rospy.Time(0)) #listen to transform between world2ee_link
    x_1 = trans_eelink[0]
    y_1 = trans_eelink[1]
    z_1 = trans_eelink[2]
    if axis_world is 'x':
        x_2 = x_1 + final_offset
        y_2 = y_1
        z_2 = z_1
    if axis_world is 'y':
        x_2 = x_1
        y_2 = y_1 + final_offset
        z_2 = z_1
    if axis_world is 'z':
        x_2 = x_1
        y_2 = y_1
        z_2 = z_1 + final_offset
    direction_vector = [x_2-x_1, y_2-y_1, z_2-z_1]
    pose_target = group.get_current_pose().pose #create a pose variable. The parameters can be seen from "$ rosmsg show Pose"
    waypoints = []
    waypoints.append(pose_target)
    t = 0 # counter/increasing variabe for the parametric equation of straight line      
    while t <= 1.01:
        pose_target.position.x = x_1 + direction_vector[0]*t
        pose_target.position.y = y_1 + direction_vector[1]*t
        pose_target.position.z = z_1 + direction_vector[2]*t
        t += resolution 
        
        waypoints.append(copy.deepcopy(pose_target))
         
    del waypoints[:1]
    plan_execute_waypoints(waypoints)
 

###___TRACK APRILTAG___###
## Detects april tag and moves to the desired position w.r.t. the detected apriltag 
# Specify the values of offset_x, offset_y, offset_z to adjust the final position of the end-effector tip 
def track_apriltag(tag_id, tag_frame_name, offset_x, offset_y, offset_z):
    rospy.sleep(1)
    resolution = 0.05 #resolution is interpreted as 1/resolution = number of interpolated points in the path
 
    msg = rospy.wait_for_message('/tag_detections', AprilTagDetectionArray, timeout = None)
    detection = False
    x = 0
    while x < 20:
        if msg.detections[x].id is tag_id:
            detection = True
            break
        x += 1
    if detection is True:
        tf_listener.waitForTransform('/world', '/ee_link', rospy.Time(), rospy.Duration(4.0))
        (trans_eelink, rot_eelink) = tf_listener.lookupTransform('/world', '/ee_link', rospy.Time(0)) #listen to transform between world2ee_link
        tf_listener.waitForTransform('/world', tag_frame_name, rospy.Time(), rospy.Duration(4.0))
        (trans_tag, rot_tag) = tf_listener.lookupTransform('/world', tag_frame_name, rospy.Time(0)) #listen to transform between world2tag_0
        i = 1
        while i is 1:

            pose_target = group.get_current_pose().pose #create a pose variable. The parameters can be seen from "$ rosmsg show Pose"
            waypoints = []
            waypoints.append(pose_target)

            tf_listener.waitForTransform('/world', '/ee_link', rospy.Time(), rospy.Duration(4.0))
            (trans_eelink, rot_eelink) = tf_listener.lookupTransform('/world', '/ee_link', rospy.Time(0)) #listen to transform between world2ee_link
            tf_listener.waitForTransform('/world', tag_frame_name, rospy.Time(), rospy.Duration(4.0))
            (trans_tag, rot_tag) = tf_listener.lookupTransform('/world', tag_frame_name, rospy.Time(0)) #listen to transform between world2tag_0
        
    
            x_1 = trans_eelink[0]
            y_1 = trans_eelink[1]
            z_1 = trans_eelink[2]
            x_2 = trans_tag[0]+offset_x     
            y_2 = trans_tag[1]+offset_y 
            z_2 = trans_tag[2] + offset_z
            v = [x_2-x_1, y_2-y_1, z_2-z_1]
            
            t = 0 # counter/increasing variabe for the parametric equation of straight line      
            while t <= 1.01:
                pose_target.position.x = x_1 + v[0]*t
                pose_target.position.y = y_1 + v[1]*t
                pose_target.position.z = z_1 + v[2]*t    
                store_x = x_1 + v[0]*t
                store_y = y_1 + v[1]*t
                store_z = z_1 + v[2]*t
   
                direction_vector = [0,0,0]
                direction_vector_normalized = [0, 0, 0]
                orthogonal_dot = [0, 0, 0]
                    
                direction_vector[0] = x_2 - store_x 
                direction_vector[1] = y_2 - store_y 
                direction_vector[2] = z_2 - store_z - offset_z
        
                #normalize direction_vector to unit length
                length = math.sqrt(direction_vector[0]*direction_vector[0]+direction_vector[1]*direction_vector[1]+direction_vector[2]*direction_vector[2])
                direction_vector_normalized[0] = direction_vector[0] / length
                direction_vector_normalized[1] = direction_vector[1] / length
                direction_vector_normalized[2] = direction_vector[2] / length
        
                #orthgonal by cross product with a standard vector e_y
                e_y = [0, 1, 0] # this parameter needs to be changed according to the general workspace of the robot 
                orthogonal_standard = numpy.cross(direction_vector_normalized, e_y)
                length = math.sqrt(orthogonal_standard[0]*orthogonal_standard[0]+orthogonal_standard[1]*orthogonal_standard[1]+orthogonal_standard[2]*orthogonal_standard[2])
                orthogonal_standard[0] = orthogonal_standard[0] / length
                orthogonal_standard[1] = orthogonal_standard[1] / length
                orthogonal_standard[2] = orthogonal_standard[2] / length 
        
                #orthogonal by cross product
                orthogonal_cross = numpy.cross(direction_vector_normalized, orthogonal_standard)

                #Fill the Rotation matrix 
                I = tf.transformations.identity_matrix()
                I[0,0] = direction_vector_normalized[0]
                I[1,0] = direction_vector_normalized[1]
                I[2,0] = direction_vector_normalized[2]
                I[0,1] = orthogonal_standard[0]
                I[1,1] = orthogonal_standard[1]    
                I[2,1] = orthogonal_standard[2]    
                I[0,2] = orthogonal_cross[0]
                I[1,2] = orthogonal_cross[1]
                I[2,2] = orthogonal_cross[2]
                I[0,3] = store_x    
                I[1,3] = store_y
                I[2,3] = store_z
                quat_from_mat = tf.transformations.quaternion_from_matrix(I)    
                
                pose_target.orientation.x = quat_from_mat[0]
                pose_target.orientation.y = quat_from_mat[1]
                pose_target.orientation.z = quat_from_mat[2]
                pose_target.orientation.w = quat_from_mat[3]
                waypoints.append(copy.deepcopy(pose_target))
                 
                t += resolution 
    
            del waypoints[:1]
            plan_execute_waypoints(waypoints)
        
            tf_listener.waitForTransform('/world', '/ee_link', rospy.Time(), rospy.Duration(4.0))
            (trans_eelink, rot_eelink) = tf_listener.lookupTransform('/world', '/ee_link', rospy.Time(0)) #listen to transform between world2ee_link
            tf_listener.waitForTransform('/world', tag_frame_name, rospy.Time(), rospy.Duration(4.0))
            (trans_tag, rot_tag) = tf_listener.lookupTransform('/world', tag_frame_name, rospy.Time(0)) #listen to transform between world2tag_0
            i = 2
    else:
        print tag_frame_name, ' not found.'  
  





#############################################################################################################################################################################################################
####____REGRASP____####
#############################################################################################################################################################################################################

###___REGRASP FUNCTION7 (CARD REGRASP)___###
## This regrasp function is modified such that psi can reach all the way to 90 degrees in one go  
def regrasp(theta, length, psi_target, object_width, axis, direction, tilt_axis, tilt_dierction, command):
    finger_length = 0.2765  ##<----------------------------------------------------------------------------------------------------------------------AROUND 0.280
    pose_target = group.get_current_pose().pose
    pose_position = [pose_target.position.x, pose_target.position.y, pose_target.position.z]
    pose_orientation = [pose_target.orientation.x, pose_target.orientation.y, pose_target.orientation.z, pose_target.orientation.w]  
    world2eelink_matrix = tf_listener.fromTranslationRotation(pose_position, pose_orientation) #change base2eelink from transform to matrix
    PointA_eelink = [finger_length, -object_width/2-object_width/4, 0, 1] ##<----------------------------------------------------------------------------TESTING
    PointA_world = numpy.matmul(world2eelink_matrix, PointA_eelink) #Caculate coordinate of point A w.r.t. /world
    
    rpy_initial = group.get_current_rpy()
    
    rpy_initial = [math.degrees(rpy_initial[0]),math.degrees(rpy_initial[1]), math.degrees(rpy_initial[2])]
    #print 'initial Pose: ', pose_target
    waypoints = []
    waypoints.append(pose_target)
    psi_current = 0.0
    while psi_current < psi_target: 
        #Calculate width
        a = length * math.cos(math.radians(psi_current))
        b = length * math.sin(math.radians(psi_current))
        c = object_width * math.cos(math.radians(psi_current))
        d = object_width * math.sin(math.radians(psi_current))
        opposite = a - d
        width = b + c
        
        #Calculate orientation
        rpy_target = [rpy_initial[0], rpy_initial[1]+psi_current, rpy_initial[2]]
        rpy_target = [math.radians(rpy_target[0]), math.radians(rpy_target[1]), math.radians(rpy_target[2])] 
        quaternion_target = tf.transformations.quaternion_from_euler(rpy_target[0], rpy_target[1], rpy_target[2])
        #Calculate position 
        if theta + psi_current <= 90:
            x = PointA_world[0] + math.fabs(finger_length*math.cos(math.radians(theta + psi_current))) + math.fabs((width/2)*math.sin(math.radians(theta+psi_current)))
            z = PointA_world[2] + math.fabs(finger_length*math.sin(math.radians(theta + psi_current))) - math.fabs((width/2)*math.cos(math.radians(theta+psi_current)))
        elif theta + psi_current > 90:
            x = PointA_world[0] - math.fabs(finger_length*math.sin(math.radians(theta + psi_current-90))) + math.fabs((width/2)*math.cos(math.radians(theta+psi_current-90)))
            z = PointA_world[2] + math.fabs(finger_length*math.cos(math.radians(theta + psi_current-90))) + math.fabs((width/2)*math.sin(math.radians(theta+psi_current-90)))
            
             
        
        #Store Values
        pose_target.position.x = x - object_width*psi_current/psi_target #<-------------------------------------------------------------------------------TESTING
        pose_target.position.z = z
        pose_target.orientation.x = quaternion_target[0]
        pose_target.orientation.y = quaternion_target[1]
        pose_target.orientation.z = quaternion_target[2]
        pose_target.orientation.w = quaternion_target[3]
        waypoints.append(copy.deepcopy(pose_target))
        psi_current += 0.5
    
    del waypoints[0]
    quat_initial = [waypoints[0].orientation.x, waypoints[0].orientation.y, waypoints[0].orientation.z, waypoints[0].orientation.w] 
    euler_initial = tf.transformations.euler_from_quaternion(quat_initial)     
    y_initial = euler_initial[1]
    y_initial = math.degrees(y_initial)
    y_previous = round(y_initial,0)
    psi_current = 0
    #del waypoints[:2] 
    regrasp_asyncExecute_waypoints(waypoints)
    
    while psi_target-1  > psi_current: #while psi is less than the desired psi
        current_pose = group.get_current_pose().pose
        quat_current = [current_pose.orientation.x, current_pose.orientation.y, current_pose.orientation.z, current_pose.orientation.w]
        euler_current = tf.transformations.euler_from_quaternion(quat_current)  
        y_current = euler_current[1]
        y_current = round(math.degrees(y_current), 0)
        if (y_current == y_previous - 1) or (y_current == y_previous + 1):           
            psi_current = psi_current + 1
            y_previous = y_current
        a = length*1000 * math.cos(math.radians(psi_current))
        b = length*1000 * math.sin(math.radians(psi_current))
        c = object_width*1000 * math.cos(math.radians(psi_current))
        d = object_width*1000 * math.sin(math.radians(psi_current))
        opposite = a - d
        width = b + c
        position = int((width - 147.41)/(-0.6783))
        gposition(pub, command, position) #increment gripper width
        
        #print opposite
    return [width/1000, opposite/1000]


    
#############################################################################################################################################################################################################
####____TUCK____####
#############################################################################################################################################################################################################
def tuck(angle_degree, opposite):
    
    finger_length = 0.2765  ##<----------------------------------------------------------------------------------------------------------------------AROUND 0.280
    pose_target = group.get_current_pose().pose
    pose_position = [pose_target.position.x, pose_target.position.y, pose_target.position.z]
    pose_orientation = [pose_target.orientation.x, pose_target.orientation.y, pose_target.orientation.z, pose_target.orientation.w]  
    world2eelink_matrix = tf_listener.fromTranslationRotation(pose_position, pose_orientation) #change base2eelink from transform to matrix
    
    msg = rospy.wait_for_message('/CModelRobotInput', inputMsg.CModel_robot_input, timeout = None)
    #Get data of gripper status and calculate width 
    gripper_position = msg.gPO
    gripper_width = ((gripper_position * (-0.6783)) + 147.41)/1000 
    PointB_eelink = [finger_length-opposite, gripper_width/2, 0, 1] 
    PointB_world = numpy.matmul(world2eelink_matrix, PointB_eelink) #Caculate coordinate of point B w.r.t. /world
    print pose_target
    print PointB_world[2], PointB_world[0]
    tilt('y', PointB_world[2], PointB_world[0], angle_degree, -1, 'yes', 'y', 1)
    
#############################################################################################################################################################################################################
####____TILT____####
#############################################################################################################################################################################################################
## Turns about a reference center point in path mode or tilt mode 
## User specifies axis:['x'/'y'/'z'], Center of Circle: [y,z / z,x / x,y], Arc turn angle: [degrees], Direction: [1/-1], Tilt Mode: ['yes'/'no'], End_effector tilt axis: ['x'/'y'/'z'], Tilt direction: [1/-1] 

def tilt(axis, CenterOfCircle_1, CenterOfCircle_2, angle_degree, direction, tilt, tilt_axis, tilt_direction):
    rospy.sleep(0.5)
    pose_target = group.get_current_pose().pose #create a pose variable. The parameters can be seen from "$ rosmsg show Pose"
    waypoints = []
    waypoints.append(pose_target)
    resolution = 2880 #Calculation of resolution by (180/resolution) degrees 
    #quaternion = [0.5, 0.5, -0.5, 0.5]
    quaternion = [pose_target.orientation.x, pose_target.orientation.y, pose_target.orientation.z, pose_target.orientation.w]
    #define the axis of rotation
    if axis is 'x' :
        position_1 = pose_target.position.y
        position_2 = pose_target.position.z
    if axis is 'y' :
        position_1 = pose_target.position.z
        position_2 = pose_target.position.x
    if axis is 'z' :
        position_1 = pose_target.position.x
        position_2 = pose_target.position.y

    circle_radius = ((position_1 - CenterOfCircle_1)**2 + (position_2 - CenterOfCircle_2)**2)**0.5 #Pyth. Theorem to find radius
    
    #calculate the global angle with respect to 0 degrees based on which quadrant the end_effector is in 
    if position_1 > CenterOfCircle_1 and position_2 > CenterOfCircle_2:
        absolute_angle = math.asin(math.fabs(position_2 - CenterOfCircle_2) / circle_radius)
    if position_1 < CenterOfCircle_1 and position_2 > CenterOfCircle_2:
        absolute_angle = math.pi - math.asin(math.fabs(position_2 - CenterOfCircle_2) / circle_radius)
    if position_1 < CenterOfCircle_1 and position_2 < CenterOfCircle_2:
        absolute_angle = math.pi + math.asin(math.fabs(position_2 - CenterOfCircle_2) / circle_radius)
    if position_1 > CenterOfCircle_1 and position_2 < CenterOfCircle_2:
        absolute_angle = 2.0*math.pi - math.asin(math.fabs(position_2 - CenterOfCircle_2) / circle_radius)
    
    #print pose_target.orientation
    theta = 0 # counter that increases the angle  
    flag = 1   
    while theta < angle_degree/180.0 * math.pi:
        if axis is 'x' :
            pose_target.position.y = circle_radius * math.cos(theta*direction+absolute_angle)+CenterOfCircle_1 #equation of circle from polar to cartesian x = r*cos(theta)+dx
            pose_target.position.z = circle_radius * math.sin(theta*direction+absolute_angle)+CenterOfCircle_2 #equation of cirlce from polar to cartesian y = r*sin(theta)+dy 
        if axis is 'y' :
            pose_target.position.z = circle_radius * math.cos(theta*direction+absolute_angle)+CenterOfCircle_1
            pose_target.position.x = circle_radius * math.sin(theta*direction+absolute_angle)+CenterOfCircle_2
        if axis is 'z' :
            pose_target.position.x = circle_radius * math.cos(theta*direction+absolute_angle)+CenterOfCircle_1
            pose_target.position.y = circle_radius * math.sin(theta*direction+absolute_angle)+CenterOfCircle_2
        
        while flag is 1:     
            euler = tf.transformations.euler_from_quaternion(quaternion) # convert quaternion to euler
            
            roll = euler[0]
            pitch = euler[1]
            yaw = euler [2] 
            flag = 2
        
        # increment the orientation angle
        if tilt_axis is 'x' :
            roll += tilt_direction*math.pi/resolution
        if tilt_axis is 'y' :
            pitch += tilt_direction*math.pi/resolution
        if tilt_axis is 'z' :
            yaw += tilt_direction*math.pi/resolution
        quaternion = tf.transformations.quaternion_from_euler(roll, pitch, yaw) # convert euler to quaternion
       
        # store values to pose_target
        pose_target.orientation.x = quaternion[0]
        pose_target.orientation.y = quaternion[1]
        pose_target.orientation.z = quaternion[2]
        pose_target.orientation.w = quaternion[3]

        waypoints.append(copy.deepcopy(pose_target))
        theta+=math.pi/resolution # increment counter, defines the number of waypoints 
    del waypoints[:2]
    plan_execute_waypoints(waypoints) 





###___Tilt for Battery Inesrtion___###
## This function is made to overcome a singularity point and also for automation of battery insertion routine 
def tilt_v2(offset, axis, angle_degree, direction, tilt_axis, tilt_direction):
    #offset = 0.28 # Offset of the reference turning point with respect x-axis downards from the ee_link origin 
    pose = group.get_current_pose()
    CenterOfCircle_1 = pose.pose.position.z-offset
    CenterOfCircle_2 = pose.pose.position.x
    tilt_v2_subfunction(axis, CenterOfCircle_1, CenterOfCircle_2, angle_degree-1, direction, 'yes', tilt_axis, tilt_direction)
    return [CenterOfCircle_1, CenterOfCircle_2]

def tilt_v2_subfunction(axis, CenterOfCircle_1, CenterOfCircle_2, angle_degree, direction, tilt, tilt_axis, tilt_direction):
    rospy.sleep(0.5)
    pose_target = group.get_current_pose().pose #create a pose variable. The parameters can be seen from "$ rosmsg show Pose"
    waypoints = []
    waypoints.append(pose_target)
    resolution = 2880 #Calculation of resolution by (180/resolution) degrees 
    quaternion = [0.5, 0.5, -0.5, 0.5]
  
    #define the axis of rotation
    if axis is 'x' :
        position_1 = pose_target.position.y
        position_2 = pose_target.position.z
    if axis is 'y' :
        position_1 = pose_target.position.z
        position_2 = pose_target.position.x
    if axis is 'z' :
        position_1 = pose_target.position.x
        position_2 = pose_target.position.y

    circle_radius = ((position_1 - CenterOfCircle_1)**2 + (position_2 - CenterOfCircle_2)**2)**0.5 #Pyth. Theorem to find radius
    
    #calculate the global angle with respect to 0 degrees based on which quadrant the end_effector is in 
    if position_1 > CenterOfCircle_1 and position_2 > CenterOfCircle_2:
        absolute_angle = math.asin(math.fabs(position_2 - CenterOfCircle_2) / circle_radius)
    if position_1 < CenterOfCircle_1 and position_2 > CenterOfCircle_2:
        absolute_angle = math.pi - math.asin(math.fabs(position_2 - CenterOfCircle_2) / circle_radius)
    if position_1 < CenterOfCircle_1 and position_2 < CenterOfCircle_2:
        absolute_angle = math.pi + math.asin(math.fabs(position_2 - CenterOfCircle_2) / circle_radius)
    if position_1 > CenterOfCircle_1 and position_2 < CenterOfCircle_2:
        absolute_angle = 2.0*math.pi - math.asin(math.fabs(position_2 - CenterOfCircle_2) / circle_radius)
    
    #print pose_target.orientation
    theta = 0 # counter that increases the angle  
    flag = 1   
    while theta < angle_degree/180.0 * math.pi:
        if axis is 'x' :
            pose_target.position.y = circle_radius * math.cos(theta*direction+absolute_angle)+CenterOfCircle_1 #equation of circle from polar to cartesian x = r*cos(theta)+dx
            pose_target.position.z = circle_radius * math.sin(theta*direction+absolute_angle)+CenterOfCircle_2 #equation of cirlce from polar to cartesian y = r*sin(theta)+dy 
        if axis is 'y' :
            pose_target.position.z = circle_radius * math.cos(theta*direction+absolute_angle)+CenterOfCircle_1
            pose_target.position.x = circle_radius * math.sin(theta*direction+absolute_angle)+CenterOfCircle_2
        if axis is 'z' :
            pose_target.position.x = circle_radius * math.cos(theta*direction+absolute_angle)+CenterOfCircle_1
            pose_target.position.y = circle_radius * math.sin(theta*direction+absolute_angle)+CenterOfCircle_2
        
        while flag is 1:     
            euler = tf.transformations.euler_from_quaternion(quaternion) # convert quaternion to euler
            
            roll = euler[0]
            pitch = euler[1]
            yaw = euler [2] 
            flag = 2
        
        # increment the orientation angle
        if tilt_axis is 'x' :
            roll += tilt_direction*math.pi/resolution
        if tilt_axis is 'y' :
            pitch += tilt_direction*math.pi/resolution
        if tilt_axis is 'z' :
            yaw += tilt_direction*math.pi/resolution
        quaternion = tf.transformations.quaternion_from_euler(roll, pitch, yaw) # convert euler to quaternion
       
        # store values to pose_target
        pose_target.orientation.x = quaternion[0]
        pose_target.orientation.y = quaternion[1]
        pose_target.orientation.z = quaternion[2]
        pose_target.orientation.w = quaternion[3]

        waypoints.append(copy.deepcopy(pose_target))
        theta+=math.pi/resolution # increment counter, defines the number of waypoints 
    del waypoints[:2]
    plan_execute_waypoints(waypoints) 


#############################################################################################################################################################################################################
####____PUSHSLIDE____####
#############################################################################################################################################################################################################

###___PUSHSLIDE___###
def push_slide(command):
    finger_length = 0.2765  ##<----------------------------------------------------------------------------------------------------------------------AROUND 0.280
    pose_target = group.get_current_pose().pose
    waypoints = []
    waypoints.append(pose_target)
    pose_position = [pose_target.position.x, pose_target.position.y, pose_target.position.z]
    pose_orientation = [pose_target.orientation.x, pose_target.orientation.y, pose_target.orientation.z, pose_target.orientation.w]  
    world2eelink_matrix = tf_listener.fromTranslationRotation(pose_position, pose_orientation) #change base2eelink from transform to matrix
    #Get data of gripper status and calculate width 
    msg = rospy.wait_for_message('/CModelRobotInput', inputMsg.CModel_robot_input, timeout = None)
    gripper_position = msg.gPO
    gripper_width = ((gripper_position * (-0.6783)) + 147.41)/1000
    target_travel_distance = gripper_width/2
    
    actual_travel_distance = 0
    while actual_travel_distance < target_travel_distance:
        eelink_eelink_0 = [0, actual_travel_distance, 0, 1]
        eelink_world_0 = numpy.matmul(world2eelink_matrix, eelink_eelink_0) # eelink coordinate transformation to world coordinate
        
        #Store Values
        pose_target.position.x = eelink_world_0[0]
        pose_target.position.z = eelink_world_0[2]
        waypoints.append(copy.deepcopy(pose_target))
        actual_travel_distance += 0.002
    del waypoints[0]
    del waypoints[0]
    
    initial_pose = group.get_current_pose().pose
    initial_position = [initial_pose.position.x, initial_pose.position.y, initial_pose.position.z]
    regrasp_asyncExecute_waypoints(waypoints)
    
    distance = 0

    while distance < target_travel_distance-0.001:
        current_pose = group.get_current_pose().pose
        current_position = [current_pose.position.x, current_pose.position.y, current_pose.position.z]
        distance = math.sqrt((initial_position[0]- current_position[0])**2+(initial_position[1]- current_position[1])**2+(initial_position[2]- current_position[2])**2)
        
        target_width = gripper_width-(2*distance)
        gripper_position = int((target_width*1000 - 147.41)/(-0.6783))
        gposition(pub, command, gripper_position) #increment gripper width
        

#############################################################################################################################################################################################################
####____MOTION PLAN____####
#############################################################################################################################################################################################################
###___Linear Path___###
## This function makes the end-effector travel in a straight path 
def linear_path(axis_world, distance, vel):
    resolution = 0.05 #resolution is interpreted as 1/resolution = number of interpolated points in the path
    pose_target = group.get_current_pose().pose
    x_1 = pose_target.position.x
    y_1 = pose_target.position.y
    z_1 = pose_target.position.z
    if axis_world is 'x':
        x_2 = x_1 + distance
        y_2 = y_1
        z_2 = z_1
    if axis_world is 'y':
        x_2 = x_1
        y_2 = y_1 + distance
        z_2 = z_1
    if axis_world is 'z':
        x_2 = x_1
        y_2 = y_1
        z_2 = z_1 + distance
    direction_vector = [x_2-x_1, y_2-y_1, z_2-z_1]
    pose_target = group.get_current_pose().pose #create a pose variable. The parameters can be seen from "$ rosmsg show Pose"
    waypoints = []
    waypoints.append(pose_target)
    t = 0 # counter/increasing variabe for the parametric equation of straight line      
    while t <= 1.01:
        pose_target.position.x = x_1 + direction_vector[0]*t
        pose_target.position.y = y_1 + direction_vector[1]*t
        pose_target.position.z = z_1 + direction_vector[2]*t
        t += resolution 
        
        waypoints.append(copy.deepcopy(pose_target))
         
    del waypoints[:1]
    plan_execute_waypoints(waypoints)

###___JOINT VALUE MANIPULATION___###
## Manipulate by assigning joint values
def assign_joint_value(joint_0, joint_1, joint_2, joint_3, joint_4, joint_5):
    group.set_max_velocity_scaling_factor(velocity)
    group_variable_values = group.get_current_joint_values() #create variable that stores joint values

    #Assign values to joints
    group_variable_values[0] = joint_0
    group_variable_values[1] = joint_1
    group_variable_values[2] = joint_2
    group_variable_values[3] = joint_3
    group_variable_values[4] = joint_4
    group_variable_values[5] = joint_5

    group.set_joint_value_target(group_variable_values) #set target joint values for 'manipulator' group
 
    plan1 = group.plan() #call plan function to plan the path (visualize on rviz)
    group.go(wait=True) #execute plan on real/simulation (gazebo) robot 
    #rospy.sleep(2) #sleep 2 seconds
    

###___RELATIVE JOINT VALUE MANIPULATION___###
## Manipulate by assigning relative joint values w.r.t. current joint values of robot
def relative_joint_value(joint_0, joint_1, joint_2, joint_3, joint_4, joint_5):
    group.set_max_velocity_scaling_factor(velocity)
    group_variable_values = group.get_current_joint_values() #create variable that stores joint values

    #Assign values to joints
    group_variable_values[0] += joint_0
    group_variable_values[1] += joint_1
    group_variable_values[2] += joint_2
    group_variable_values[3] += joint_3
    group_variable_values[4] += joint_4
    group_variable_values[5] += joint_5

    group.set_joint_value_target(group_variable_values) #set target joint values for 'manipulator' group
 
    plan1 = group.plan() #call plan function to plan the path (visualize on rviz)
    group.go(wait=True) #execute plan on real/simulation (gazebo) robot 
   
def plan_execute_waypoints(waypoints):
    (plan3, fraction) = group.compute_cartesian_path(waypoints, 0.01, 0) #parameters(waypoints, resolution_1cm, jump_threshold)
    plan= group.retime_trajectory(robot.get_current_state(), plan3, velocity) #parameter that changes velocity
    group.execute(plan)
 
def regrasp_asyncExecute_waypoints(waypoints):
    (plan3, fraction) = group.compute_cartesian_path(waypoints, 0.01, 0) #parameters(waypoints, resolution_1cm, jump_threshold)
    plan= group.retime_trajectory(robot.get_current_state(), plan3, velocity) #parameter that changes velocity
    group.execute(plan, wait = False)

def forceseek_asyncExecute_waypoints(waypoints):
    (plan3, fraction) = group.compute_cartesian_path(waypoints, 0.01, 0) #parameters(waypoints, resolution_1cm, jump_threshold)
    plan= group.retime_trajectory(robot.get_current_state(), plan3, 0.002) #parameter that changes velocity
    group.execute(plan, wait = False)


#############################################################################################################################################################################################################
####____PLANNING SCENE____####
#############################################################################################################################################################################################################

def add_object(name, frame_id, pos_x, pos_y, pos_z, ori_x, ori_y, ori_z, ori_w, size_x, size_y, size_z):
    p = group.get_current_pose()
    p.header.frame_id = frame_id
    p.pose.position.x = pos_x
    p.pose.position.y = pos_y
    p.pose.position.z = pos_z
    p.pose.orientation.x = ori_x
    p.pose.orientation.y = ori_y
    p.pose.orientation.z = ori_z
    p.pose.orientation.w = ori_w 
    scene.add_box(name, p, (size_x, size_y, size_z))
    rospy.sleep(2)

def add_object_file(name, pos_x, pos_y, pos_z, ori_x, ori_y, ori_z, ori_w, filename):
    p = group.get_current_pose()
    p.pose.position.x = pos_x
    p.pose.position.y = pos_y
    p.pose.position.z = pos_z
    p.pose.orientation.x = ori_x
    p.pose.orientation.y = ori_y
    p.pose.orientation.z = ori_z
    p.pose.orientation.w = ori_w 
    scene.add_mesh(name, p, filename)
    rospy.sleep(2)
    
def remove_object(name):
    scene.remove_world_object(name)


#############################################################################################################################################################################################################
####____STATUS____####
#############################################################################################################################################################################################################


###___STATUS ROBOT___###
def manipulator_status():
    #You can get a list with all the groups of the robot like this:
    print "Robot Groups:"
    print robot.get_group_names()

    #You can get the current values of the joints like this:
    print "Current Joint Values:"
    print group.get_current_joint_values()

    #You can also get the current Pose of the end effector of the robot like this:
    print "Current Pose:"
    print group.get_current_pose()

    #Finally you can check the general status of the robot like this:
    print "Robot State:"
    print robot.get_current_state()

#############################################################################################################################################################################################################
####____MAIN____####
#############################################################################################################################################################################################################
###___Initiate node; subscribe to topic; call callback function___###
def manipulator_arm_control():
    global velocity
###___Add Collision Objects___###
    #remove_object('ee')
    #add_object('table', 'world', 0, 0, -0.05, 0, 0, 0, 1, 2, 2, 0.05)
    #add_object('ee', 'ee_link', 0.14, 0, 0, 0, 0, 0, 1, 0.28, 0.03, 0.1)
    
###___MOTION PLAN TO SET ROBOT TO REAL ENVIRONMNET for GAZEBO___###
#    relative_joint_value(0, -math.pi/2, 0, 0, 0, 0)
#    relative_joint_value(0, 0, -3*math.pi/4, 0, 0, 0)
#    relative_joint_value(0, 0, 0, -3*math.pi/4, 0, 0)
#    relative_joint_value(0, 0, 0, 0, -math.pi/2, 0) 


###___CARD INSERTION ROUTINE___###
##################################################################################################
###___PICK UP CARD ROUTINE___###
#    object_length = 0.0853 #object total length in meters
#    object_width = 0.005
#    delta_0 = 0.035 #insertion length in meters
#    theta_0 = 40 #target theta
#    psi_0 = 20
#    #offset = 0.2765 + object_length - delta_0  
#    offset = 0.2845 + object_length - delta_0  #Offset for new fingers
#    command = gactive(pub)
#    rospy.sleep(0.5) 
#    gposition(pub, command, 215)
#    assign_joint_value(0.025, -2.114, -1.034, -4.706, -1.569, 1.597)  #WIDE VIEW POSITION
#    rospy.sleep(1)
#    track_apriltag(6, '/tag_6', -0.038, 0.024, 0.40)
#    rospy.sleep(1)
#    force_seek('z', -0.1, 'z', 5, 0.003, 0.01)
#    pickup(command, -delta_0, 0.05)


#####___GO TO CARD RECEPTACLE AND INSERTION ROUTINE___###
#    assign_joint_value(0.025, -2.114, -1.034, -4.706, -1.569, 1.597) # WIDE VIEW POSITION    
#    track_apriltag(5, '/tag_5', -0.10, 0.0195, 0.405)
#    rospy.sleep(1)
#    force_seek('z', -0.1, 'z', 5, 0.002, 0.01)
#    rospy.sleep(1)
#    force_seek('x', -0.1, 'x', 5, 0.001, 0.01)
#    pivot = tilt_v2(offset, 'y', 90-theta_0, 1, 'y', 1)
#    rospy.sleep(1)
#    [width, opposite] = regrasp(theta_0, delta_0, 70, object_width, 'y', 1, 'y', 1, command)
#    rospy.sleep(1)
#    tilt('y', pivot[0], pivot[1], 20, 1, 'yes', 'y', 1)
#    tuck(10, 0)
#    rospy.sleep(0.5)    
#    assign_joint_value(0.025, -2.114, -1.034, -4.706, -1.569, 1.597)
################################################################################################
    

   
#####EXPERIMENT PUSH SLIDE FOR ROBOT MANIPULATION
#    object_length = 0.0853 #object total length in meters
#    object_width = 0.005
#    delta_0 = 0.035 #insertion length in meters
#    theta_0 = 40 #target theta
#    psi_0 = 20
#    #offset = 0.2765 + object_length - delta_0  
#    offset = 0.2845 + object_length - delta_0  #Offset for new fingers
#    command = gactive(pub)
#    rospy.sleep(0.5) 
#    gposition(pub, command, 215)
#    assign_joint_value(-0.1418, -1.9215, -1.6372, -4.2984, -1.5724, 1.4292)
#    rospy.sleep(1)
#    force_seek('z', -0.1, 'z', 5, 0.003, 0.01)
#    pickup(command, -delta_0+0.008, 0.05)
#    assign_joint_value(-0.4219, -2.0900, -1.4667, -4.3044, -1.5679, 1.1467)
#    rospy.sleep(1)
#    force_seek('z', -0.1, 'z', 5, 0.002, 0.01)
#    pivot = tilt_v2(offset+0.006, 'y', 90-theta_0, 1, 'y', 1)
#    rospy.sleep(1)
#    [width, opposite] = regrasp(theta_0, delta_0, psi_0, object_width, 'y', 1, 'y', 1, command)
#    rospy.sleep(1)
#    velocity = 0.01
#    tilt('y', pivot[0], pivot[1], 22, 1, 'yes', 'y', -1)
#    velocity = 0.0001
#    push_slide(command)

#####################################################################################################

    object_length = 0.0853 #object total length in meters
    object_width = 0.005
    delta_0 = 0.035 #insertion length in meters
    theta_0 = 30 #target theta
    psi_0 = 90
    offset = 0.2845 + object_length - delta_0  #Offset for new fingers
    command = gactive(pub)
    assign_joint_value(0.025, -2.114, -1.034, -4.706, -1.569, 1.597) # WIDE VIEW POSITION 
    rospy.sleep(0.1)
    contact_G = tilt_v2(offset, 'y', 90-theta_0, 1, 'y', 1)
    [width, opposite] = regrasp_tilt(theta_0, delta_0, psi_0, object_width, 'y', 1, 'y', 1, contact_G, command)
    rospy.sleep(2)
    reference_marker([contact_G[1], 0.14474, contact_G[0]], color='red', assign_id = 1000)
    



    #manipulator_status() #debug
    rospy.spin()






##REGRASP-TILT###############################################################################################################################################################
def regrasp_tilt(theta, length, psi_target, object_width, axis, direction, tilt_axis, tilt_dierction, contact_G, command):
    finger_length = 0.2765  ##<----------------------------------------------------------------------------------------------------------------------AROUND 0.280
    pose_target = group.get_current_pose().pose
    pose_position = [pose_target.position.x, pose_target.position.y, pose_target.position.z]
    pose_orientation = [pose_target.orientation.x, pose_target.orientation.y, pose_target.orientation.z, pose_target.orientation.w]  
    world2eelink_matrix = tf_listener.fromTranslationRotation(pose_position, pose_orientation) #change base2eelink from transform to matrix
    PointA_eelink = [finger_length, -object_width/2-object_width/4, 0, 1] ##<----------------------------------------------------------------------------TESTING
    PointA_world = numpy.matmul(world2eelink_matrix, PointA_eelink) #Caculate coordinate of point A w.r.t. /world
    
    rpy_initial = group.get_current_rpy()
    
    rpy_initial = [math.degrees(rpy_initial[0]),math.degrees(rpy_initial[1]), math.degrees(rpy_initial[2])]
    regrasp_waypoints = []
    regrasp_waypoints.append(pose_target)
    psi_current = 0.0
    while psi_current < psi_target: 
        #Calculate width
        a = length * math.cos(math.radians(psi_current))
        b = length * math.sin(math.radians(psi_current))
        c = object_width * math.cos(math.radians(psi_current))
        d = object_width * math.sin(math.radians(psi_current))
        opposite = a - d
        width = b + c
        
        #Calculate orientation
        rpy_target = [rpy_initial[0], rpy_initial[1]+psi_current, rpy_initial[2]]
        rpy_target = [math.radians(rpy_target[0]), math.radians(rpy_target[1]), math.radians(rpy_target[2])] 
        quaternion_target = tf.transformations.quaternion_from_euler(rpy_target[0], rpy_target[1], rpy_target[2])
        #Calculate position 
        if theta + psi_current <= 90:
            x = PointA_world[0] + math.fabs(finger_length*math.cos(math.radians(theta + psi_current))) + math.fabs((width/2)*math.sin(math.radians(theta+psi_current)))
            z = PointA_world[2] + math.fabs(finger_length*math.sin(math.radians(theta + psi_current))) - math.fabs((width/2)*math.cos(math.radians(theta+psi_current)))
        elif theta + psi_current > 90:
            x = PointA_world[0] - math.fabs(finger_length*math.sin(math.radians(theta + psi_current-90))) + math.fabs((width/2)*math.cos(math.radians(theta+psi_current-90)))
            z = PointA_world[2] + math.fabs(finger_length*math.cos(math.radians(theta + psi_current-90))) + math.fabs((width/2)*math.sin(math.radians(theta+psi_current-90)))
            
             
        
        #Store Values
        pose_target.position.x = x - object_width*psi_current/psi_target #<-------------------------------------------------------------------------------TESTING
        pose_target.position.z = z
        pose_target.orientation.x = quaternion_target[0]
        pose_target.orientation.y = quaternion_target[1]
        pose_target.orientation.z = quaternion_target[2]
        pose_target.orientation.w = quaternion_target[3]
        regrasp_waypoints.append(copy.deepcopy(pose_target))
        psi_current += 0.5
    
    del regrasp_waypoints[0]
    
      
    #Construct a transform matrix that can rotate the regrasp_waypoints according to tiliting about contact G
    transform = tf.transformations.identity_matrix()
    # <u,v,w> is a unit vector to rotate about the line that passes through the point (x,y,z)
    [x, y, z] = [contact_G[1], 0, contact_G[0]]
    [u, v, w] = [0, 1, 0]
    new_waypoints = []
    pose_target = group.get_current_pose().pose
    new_waypoints.append(pose_target)
    for i in range(len(regrasp_waypoints)):
        desired = (float(theta)/float(len(regrasp_waypoints)))*i 
        transform[0][0] = u**2 + (v**2+w**2)*math.cos(math.radians(desired))
        transform[1][0] = u*v*(1-math.cos(math.radians(desired)))+w*math.sin(math.radians(desired)) 
        transform[2][0] = u*w*(1-math.cos(math.radians(desired)))-v*math.sin(math.radians(desired))
        transform[3][0] = 0 
        transform[0][1] = u*v*(1-math.cos(math.radians(desired)))-w*math.sin(math.radians(desired))
        transform[1][1] = v**2 + (u**2+w**2)*math.cos(math.radians(desired))
        transform[2][1] = v*w*(1-math.cos(math.radians(desired)))+u*math.sin(math.radians(desired))
        transform[3][1] = 0
        transform[0][2] = u*w*(1-math.cos(math.radians(desired)))+v*math.sin(math.radians(desired))
        transform[1][2] = v*w*(1-math.cos(math.radians(desired)))-u*math.sin(math.radians(desired))
        transform[2][2] = w**2 + (u**2+v**2)*math.cos(math.radians(desired))
        transform[3][2] = 0
        transform[0][3] = (x*(v**2+w**2)-u*(y*v+z*w))*(1-math.cos(math.radians(desired)))+(y*w-z*v)*math.sin(math.radians(desired))
        transform[1][3] = (y*(u**2+w**2)-v*(x*u+z*w))*(1-math.cos(math.radians(desired)))+(z*u-x*w)*math.sin(math.radians(desired))
        transform[2][3] = (z*(u**2+v**2)-w*(x*u+y*v))*(1-math.cos(math.radians(desired)))+(x*v-y*u)*math.sin(math.radians(desired))
        transform[3][3] = 1

        waypoint_position = [regrasp_waypoints[i].position.x, regrasp_waypoints[i].position.y, regrasp_waypoints[i].position.z, 1] 
        waypoint_orientation = [regrasp_waypoints[i].orientation.x, regrasp_waypoints[i].orientation.y, regrasp_waypoints[i].orientation.z, regrasp_waypoints[i].orientation.w]  
        waypoint_matrix = tf_listener.fromTranslationRotation(waypoint_position, waypoint_orientation) #change base2eelink from transform to matrix
        #Multily the transform with the regrasp waypoint positions to get new waypoints
        new_position = numpy.matmul(transform, waypoint_position)

        #Extract 3x3 rotation matrix from transform and regrasp waypoint and multiply to get new waypoint orientation        
        transform_extracted = [transform[0][:3],transform[1][:3],transform[2][:3]]
        waypoint_extracted = [waypoint_matrix[0][:3],waypoint_matrix[1][:3],waypoint_matrix[2][:3]]
        new_orientation_matrix = numpy.matmul(transform_extracted, waypoint_extracted)  
        
        new_euler = tf.transformations.euler_from_matrix(new_orientation_matrix)
        new_quat = tf.transformations.quaternion_from_euler(new_euler[0], new_euler[1], new_euler[2])
        #CORRECT NEW WAYPOINT TRAJECTORY FOR REGRASPING AND TILITING SIMULTANEIOUSLY
        pose_target.position.x = new_position[0]
        pose_target.position.y = new_position[1]
        pose_target.position.z = new_position[2]
        pose_target.orientation.x = new_quat[0]
        pose_target.orientation.y = new_quat[1]
        pose_target.orientation.z = new_quat[2]
        pose_target.orientation.w = new_quat[3]

        new_waypoints.append(copy.deepcopy(pose_target))

    del new_waypoints[0]

    #GRIPPER WIDTH CONTROL
    quat_initial = [regrasp_waypoints[0].orientation.x, regrasp_waypoints[0].orientation.y, regrasp_waypoints[0].orientation.z, regrasp_waypoints[0].orientation.w] 
    euler_initial = tf.transformations.euler_from_quaternion(quat_initial)     
    y_initial = math.degrees(euler_initial[1])
    y_previous = round(y_initial,0)
    psi_current = 0
    
    regrasp_asyncExecute_waypoints(new_waypoints)
    while psi_target-2  > psi_current: #while psi is less than the desired psi
        current_pose = group.get_current_pose().pose
        quat_current = [current_pose.orientation.x, current_pose.orientation.y, current_pose.orientation.z, current_pose.orientation.w]
        euler_current = tf.transformations.euler_from_quaternion(quat_current)  
        y_current = round(math.degrees(euler_current[1]), 0)
        psi_current = psi_target*((y_current-y_initial)/(psi_target-theta))
#        print y_initial, y_current
#        if (y_current == y_previous - 1) or (y_current == y_previous + 1):           
#            psi_current = psi_current + 1
#            y_previous = y_current
        a = length*1000 * math.cos(math.radians(psi_current))
        b = length*1000 * math.sin(math.radians(psi_current))
        c = object_width*1000 * math.cos(math.radians(psi_current))
        d = object_width*1000 * math.sin(math.radians(psi_current))
        opposite = a - d
        width = b + c
        position = int((width - 147.41)/(-0.6783))
        gposition(pub, command, position) #increment gripper width
       
    waypoints_marker(new_waypoints, 'blue', 0)
    waypoints_marker(regrasp_waypoints, 'red', 500)
    
    return [width/1000, opposite/1000]


###___MAIN___###
if __name__ == '__main__':

    try:
        
        manipulator_arm_control()
        
        moveit_commander.roscpp_shutdown() #shut down the moveit_commander

    except rospy.ROSInterruptException: pass
