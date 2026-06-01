import time
import asyncio
from sdk.commands.move_coordinates_command import MoveCoordinatesParamsPosition, MoveCoordinatesParamsOrientation, PlannerType
from sdk.manipulators.m13 import M13

host = "10.100.21.86" # IP манипулятора
client_id = "client_id" # ID клиента
login = "login" # Логин
password = "password" # Пароль
manipulator = M13(host, client_id, login, password)

position = MoveCoordinatesParamsPosition(0.71, 0.0, 0.27)
orientation = MoveCoordinatesParamsOrientation(0, 0, 0, 1.0)

p = [MoveCoordinatesParamsPosition(0.7, 0.0, 0.27), MoveCoordinatesParamsPosition(0.75, 0.0, 0.27), MoveCoordinatesParamsPosition(0.75, -0.05, 0.27), MoveCoordinatesParamsPosition(0.7, -0.05, 0.27)]
vf = 0.2
af = 0.2
async def make_manipulator_connection():
    try:
        manipulator.connect()
        manipulator.get_control()
        for _ in range(4):
            for i in range(4):
                manipulator.move_to_coordinates(p[i], orientation, velocity_scaling_factor=vf, acceleration_scaling_factor=af)
    except Exception as e:
        print("Error: ", e)

        
time.sleep(3)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
asyncio.get_event_loop().run_until_complete(make_manipulator_connection())