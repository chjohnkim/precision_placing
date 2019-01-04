##GRIPPER
def gactive(pub)
def greset(pub)
def gposition(pub,command, position)
def pickup(command, distance, vel)

##THIRD FINGER
def final_push()

##SENSING
def force_seek(axis_world, distance, force_direction, sensitivity, final_offset, vel)
def point_apriltag(tag_id, tag_frame_name)
def track_apriltag(tag_id, tag_frame_name, offset_x, offset_y, offset_z)

##REGRASP
def regrasp4(theta, length, psi_target, object_width, axis, direction, tilt_axis, tilt_direction, command)
def regrasp3(theta, length, psi_target, object_width, axis, direction, tilt_axis, tilt_direction, command)
def regrasp2(theta, length, psi_target, object_width, axis, direction, tilt_axis, tilt_direction, command)
def regrasp1(theta, length, psi_target, axis, direction, tilt_axis, tilt_direction, command)

##MOTION PLAN
def TurnArc_Battery(offset, axis, angle_degree, direction, tilt_axis, tilt_direction)
def TurnArcAboutAxis_Battery(axis, CenterOfCircle_1, CenterOfCircle_2, angle_degree, direction, tilt, tilt_axis, tilt_direction)
def TurnArcAboutAxis(axis, CenterOfCircle_1, CenterOfCircle_2, angle_degree, direction, tilt, tilt_axis, tilt_direction)
def TiltAboutAxis(pose_target, resolution, tilt_axis, tilt_direction)
def get_instantaneous_center(opposite, rate_hz)
def two_points_linear_path()
def assign_joint_value(joint_0, joint_1, joint_2, joint_3, joint_4, joint_5)
def assign_pose_target(pos_x, pos_y, pos_z, orient_x, orient_y, orient_z, orient_w)
def relative_joint_value(joint_0, joint_1, joint_2, joint_3, joint_4, joint_5)
def relative_pose_target(axis_world, distance)

##EXECUTE
def plan_execute_waypoints(waypoints)
def plan_asyncExecute_waypoints(waypoints)

##STATUS
def manipulator_status()

##MAIN
def manipulator_arm_control()
