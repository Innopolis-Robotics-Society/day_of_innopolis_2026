import time
import math
import asyncio
from sdk.commands.move_coordinates_command import MoveCoordinatesParamsPosition, MoveCoordinatesParamsOrientation, PlannerType
from sdk.manipulators.m13 import M13
from dataclasses import dataclass, field
# from sdk.commands.arc_motion import Pose, Position, Orientation
from sdk.commands.data import Pose, Point, Position, Orientation
import json
host = "10.100.21.86" # IP манипулятора
client_id = "client_id" # ID клиента
login = "login" # Логин
password = "password" # Пароль
manipulator = M13(host, client_id, login, password)

vMove = 0.1
vWrite = 0.4
af = 0.1

def interpolate_circle(R: float, xc: float, yc: float, z: float, dt: float, V: float):
    L = V*dt
    delta = (L * 180) / (math.pi*R)
    print(L, delta)
    pos = []
    for i in range(int(360/delta)):
        pos.append((xc + R*math.cos(math.radians(delta*i)),
                   yc + R*math.sin(math.radians(delta*i)), 
                   z))
    pos.append(pos[0])
    return pos

def interpolate_spiral(alpha: float, Rmax: float, xc: float, yc: float, z: float, delta: float):
    pos = []
    for i in range(2*int(360/delta)):
        angle = delta*i
        R = alpha * angle/360
        pos.append((round(xc + R*math.cos(math.radians(angle)), 4), round(yc + R*math.sin(math.radians(angle)), 4), z))
    return pos

import csv
import glob
import os

def load_trajectories(folder="trajectory"):
    trajectories = []
    files = sorted(glob.glob(os.path.join(folder, "*.csv")))
    for filename in files:
        trajectory = []
        with open(filename, "r") as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                trajectory.append([
                    float(row[0]),
                    float(row[1])
                ])
        trajectories.append(trajectory)
    return trajectories

orientation = Orientation(0, 0, 0, 1.0)
V = 0.1
dt = 0.01
eps = 0.000001
L = dt*V
h = 0.1615
x = 0.78
y = 0.105

async def make_manipulator_connection():
    global dt, V, eps, L
    try:
        manipulator.connect()
        manipulator.get_control()
        # poses = interpolate_spiral(0.025, 0.1, x, y, h, 1)
        # pf1 = MoveCoordinatesParamsPosition(x, y, h)
        linear_vel = {"x": 0, "y": 0, "z": 0}
        angular_vel = {"rx": 0, "ry": 0, "rz": 0}
        poseses = load_trajectories()
        for poss in poseses:
            poses = []
            for i in range(len(poss)):
                poses.append([poss[i][0] + x, -poss[i][1] + y, h])
            manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(*poses[0][:2], h+0.015), orientation, velocity_scaling_factor=vWrite, acceleration_scaling_factor=af)
            manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(*poses[0]), orientation, velocity_scaling_factor=vMove, acceleration_scaling_factor=af)
            manipulator.set_servo_twist_mode()
            for i in range(1, len(poses)):
                # await manipulator.stream_coordinates_async(MoveCoordinatesParamsPosition(*pos), orientation)
                # time.sleep(0.04)
                dx, dy = poses[i][0] - poses[i-1][0], poses[i][1] - poses[i-1][1]
                L = math.hypot(dx, dy)
                vx, vy = V * (dx / L), V * (dy / L)
                # vx, vy = math.cos(math.radians(i)), math.sin(math.radians(i))
                linear_vel["x"] = vx
                linear_vel["y"] = vy
                await manipulator.stream_cartesian_velocities_async(linear_vel, angular_vel)
                await asyncio.sleep(dt)
            manipulator.set_servo_pose_mode()
            manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(*poses[-1][:2], h+0.015), orientation, velocity_scaling_factor=vMove, acceleration_scaling_factor=af)
        manipulator.stop_movement()
        # pf2 = MoveCoordinatesParamsPosition(x, y, h+0.1)
        # manipulator.move_to_coordinates(pf2, orientation, velocity_scaling_factor=vMove, acceleration_scaling_factor=af)
        # manipulator.move_to_coordinates(pf1, orientation, velocity_scaling_factor=vMove, acceleration_scaling_factor=af)
        # # manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(*poses[0]), orientation, velocity_scaling_factor=vMove, acceleration_scaling_factor=af)
        # manipulator.set_servo_twist_mode()
        # time.sleep(0.5)
        # poses = interpolate_circle(0.1, x, y, h, dt, V)
        # print(poses)
        # v = 0.1
        # linear_vel = {"x": 0.0, 
        #                 "y": -v, 
        #                 "z": 0}
        # angular_vel = {"rx": 0, "ry": 0, "rz": 0}
        # a = json.loads(manipulator.get_cartesian_coordinates())
        # print("Start moving")
        # # t0 = time.time()
        # yc = a["tool0"]["position"]["y"]
        # print(yc)
        # yf = yc
        # while yc > yf - 0.03:
        #     await manipulator.stream_cartesian_velocities_async(linear_vel, angular_vel)
        #     a = manipulator.get_cartesian_coordinates()
        #     a = json.loads(a)
        #     yc = a["tool0"]["position"]["y"]
        #     if yc <= yf - 0.03:
        #         break
        #     # time.sleep(0.001)
        # print("Stop")
        # linear_vel = {"x": 0.0, 
        #               "y": 0,
        #               "z": 0}
        # manipulator.stream_cartesian_velocities(linear_vel, angular_vel)
            # t1 = time.time()
            # print(t1 - t0)
            # t0 = t1
        # linear_vel = {"x": v, 
        #                 "y": 0.0, 
        #                 "z": 0}
        # while a["tool0"]["position"]["x"] < x + 0.05:
        #     manipulator.stream_cartesian_velocities(linear_vel, angular_vel)
        #     a = json.loads(manipulator.get_cartesian_coordinates())
        
        # linear_vel = {"x": 0.0, 
        #                 "y": v, 
        #                 "z": 0}
        # while a["tool0"]["position"]["y"] < y:
        #     manipulator.stream_cartesian_velocities(linear_vel, angular_vel)
        #     a = json.loads(manipulator.get_cartesian_coordinates())
        # linear_vel = {"x": -v, 
        #                 "y": 0.0, 
        #                 "z": 0}
        # while a["tool0"]["position"]["x"] > x:
        #     manipulator.stream_cartesian_velocities(linear_vel, angular_vel)
        #     a = json.loads(manipulator.get_cartesian_coordinates())
        # print("Move")
        # g = []
        # for i in range(1, len(poses)//2):
        #     g.append(math.hypot(poses[i][0] - poses[i-1][0], poses[i][1] - poses[i-1][1]))
        # print(g)
        # for i in range(1, len(poses)//2):
        #     dx, dy = poses[i-1][0] - poses[i][0], poses[i-1][1] - poses[i][1]
        #     vx, vy = V * (dx / L), V * (dy / L)
        #     linear_vel = {"x": vx, 
        #                   "y": vy, 
        #                   "z": 0}
        #     angular_vel = {"rx": 0, "ry": 0, "rz": 0}
        #     await manipulator.stream_cartesian_velocities_async(linear_vel, angular_vel)
        #     await asyncio.sleep(dt)
        # manipulator.stop_movement()
        # linear_vel = {"x": 0, "y": 0, "z": 0}
        # angular_vel = {"rx": 0, "ry": 0, "rz": 0}
        # for i in range(360):
        #     # dx, dy = poses[i-1][0] - poses[i][0], poses[i-1][1] - poses[i][1]
        #     # vx, vy = V * (dx / L), V * (dy / L)
        #     vx, vy = math.cos(math.radians(i)), math.sin(math.radians(i))
        #     linear_vel["x"] = vx/10
        #     linear_vel["y"] = vy/10
        #     await manipulator.stream_cartesian_velocities_async(linear_vel, angular_vel)
        #     # await asyncio.sleep(0.01)
        # manipulator.stop_movement()
        # time.sleep(0.5)
        # manipulator.set_servo_pose_mode()
        # manipulator.move_to_coordinates(pf2, orientation, velocity_scaling_factor=vMove, acceleration_scaling_factor=af, timeout_seconds=10.0)
        # x2, y2 = 0.6, y
        
        # poses = interpolate_circle(0.06, x2, y2, h, dt, V)
        # manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(*poses[0]), orientation, velocity_scaling_factor=vMove, acceleration_scaling_factor=af)
        # for i in range(1, len(poses)):
        #     dx, dy = poses[i-1][0] - poses[i][0], poses[i-1][1] - poses[i][1]
        #     vx, vy = V * (dx / L), V * (dy / L)
        #     linear_vel = {"x": vx, 
        #                   "y": vy, 
        #                   "z": 0}
        #     angular_vel = {"rx": 0, "ry": 0, "rz": 0}
        #     manipulator.stream_cartesian_velocities(linear_vel, angular_vel)
        #     time.sleep(dt+eps)
        time.sleep(1)
    except Exception as e:
        print("Error: ", e)

        
time.sleep(3)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
asyncio.get_event_loop().run_until_complete(make_manipulator_connection())
