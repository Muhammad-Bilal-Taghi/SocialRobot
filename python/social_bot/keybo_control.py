# Copyright (c) 2019 Horizon Robotics. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys, tty, termios
import select
import numpy as np
from absl import logging


# Get command from keyboard
class KeyboardControl:
    """
    This class is used to generate demonstrations from human through keyboard.
    Note that you should keep the terminal window on the fore-front to capture
    the key being pressed.
    Some tricks are used to make the keyboard controlling a little bit more
    friendly. Move the agent around by key "WASD" and open or close gripper by
    key "E", and control the robot arm(if there is) by "IJKL".
    """

    def __init__(self):
        self._speed = 0
        self._turning = 0
        self._gripper_pos = [0, 0, 0]
        self._gripper_open = True
        self._wheel_step = 0.5
        self._gripper_step = 0.02
        self._speed_decay = 0.9
        self._turning_decay = 0.5

    def reset(self):
        self._gripper_pos = [0, 0, 0]
        self._gripper_open = True
        self._speed = 0
        self._turning = 0

    def _get_key(self):
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno(), termios.TCSANOW)
            if select.select([sys.stdin], [], [], 0.0)[0]:
                key = sys.stdin.read(1)
            else:
                key = None
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return key

    def get_agent_actions(self, agent_type):
        """
        Args:
            agent_type(sting): the agent type
        Returns:
            actions generated by the keyboard accroding to agent type
        """
        key = self._get_key()
        self._speed *= self._speed_decay
        self._turning *= self._turning_decay
        # movemnts
        if key == "w":
            self._speed = 0 if self._speed < -0.01 else self._speed + self._wheel_step
        elif key == "s":
            self._speed = 0 if self._speed > 0.01 else self._speed - self._wheel_step
        elif key == "a":
            self._turning = 0 if self._turning > 0.01 else self._turning - self._wheel_step
        elif key == "d":
            self._turning = 0 if self._turning < -0.01 else self._turning + self._wheel_step
        # gripper pose
        elif key == "i":
            self._gripper_pos[0] -= self._gripper_step
        elif key == "k":
            self._gripper_pos[0] += self._gripper_step
        elif key == "j":
            self._gripper_pos[1] -= self._gripper_step
        elif key == "l":
            self._gripper_pos[1] += self._gripper_step
        # gripper finger
        elif key == "e":
            self._gripper_open = not self._gripper_open
        # set step size
        elif key == "+":
            self._wheel_step *= 1.5
            self._gripper_step *= 1.5
        elif key == "-":
            self._wheel_step *= 0.7
            self._gripper_step *= 0.7

        return self._convert_to_agent_action(agent_type)

    def _convert_to_agent_action(self, agent_type):
        if agent_type == 'pioneer2dx_noplugin' or agent_type == 'turtlebot':
            actions = self._to_diff_drive_action()
        elif agent_type == 'youbot_noplugin':
            actions = self._to_youbot_action()
        elif agent_type == 'pr2_noplugin':
            actions = self._to_pr2_action()
        else:
            actions = []
            logging.info("agent type not supported yet: " + agent_type)
        return actions

    def _to_diff_drive_action(self):
        left_wheel_joint = self._speed + self._turning
        right_wheel_joint = self._speed - self._turning
        actions = [left_wheel_joint, right_wheel_joint]
        return actions

    def _to_youbot_action(self):
        wheel_joint_bl = self._speed + self._turning
        wheel_joint_br = self._speed - self._turning
        wheel_joint_fl = self._speed + self._turning
        wheel_joint_fr = self._speed - self._turning
        if self._gripper_open:
            gripper_joint = 0.5
        else:
            gripper_joint = -0.5
        actions = [
            # arm joints
            0,
            0.5 + self._gripper_pos[1],
            0.3,
            self._gripper_pos[0] - 0.1,
            0.2,
            0,
            # palm joint and gripper joints
            0,
            gripper_joint,
            gripper_joint,
            # wheel joints
            wheel_joint_bl,
            wheel_joint_br,
            wheel_joint_fl,
            wheel_joint_fr
        ]
        return actions

    def _to_pr2_action(self):
        wheel_joint_bl = self._speed + self._turning
        wheel_joint_br = self._speed - self._turning
        wheel_joint_fl = self._speed + self._turning
        wheel_joint_fr = self._speed - self._turning
        actions = [
            wheel_joint_fl, wheel_joint_fl, wheel_joint_fr, wheel_joint_fr,
            wheel_joint_bl, wheel_joint_bl, wheel_joint_br, wheel_joint_br
        ]
        return actions


def main():
    """
    Simple testing of KeyboardControl class.
    """
    import matplotlib.pyplot as plt
    import time
    import social_bot
    from social_bot.envs.play_ground import PlayGround
    from social_bot.tasks import GoalTask, KickingBallTask, ICubAuxiliaryTask
    use_image_obs = False
    fig = None
    agent_type = 'youbot_noplugin'
    env = PlayGround(
        with_language=False,
        use_image_observation=use_image_obs,
        image_with_internal_states=False,
        agent_type=agent_type,
        max_steps=100000,
        real_time_update_rate=500,
        tasks=[GoalTask])
    env.render()
    keybo = KeyboardControl()
    step_cnt = 0
    last_done_time = time.time()
    while True:
        actions = np.array(keybo.get_agent_actions(agent_type))
        obs, _, done, _ = env.step(actions)
        step_cnt += 1
        if use_image_obs:
            if fig is None:
                fig = plt.imshow(obs)
            else:
                fig.set_data(obs)
            plt.pause(0.00001)
        if done:
            env.reset()
            keybo.reset()
            step_per_sec = step_cnt / (time.time() - last_done_time)
            logging.info("step per second: " + str(step_per_sec))
            step_cnt = 0
            last_done_time = time.time()


if __name__ == "__main__":
    logging.set_verbosity(logging.INFO)
    main()