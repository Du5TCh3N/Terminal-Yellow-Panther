import gamelib
import random
import math
import warnings
from sys import maxsize
import json
import copy

"""
Most of the algo code you write will be in this file unless you create new
modules yourself. Start by modifying the 'on_turn' function.

Advanced strategy tips: 

  - You can analyze action frames by modifying on_action_frame function

  - The GameState.map object can be manually manipulated to create hypothetical 
  board states. Though, we recommended making a copy of the map to preserve 
  the actual current map state.
"""


class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))

    def on_game_start(self, config):
        """
        Read in config and perform any initial setup here
        """
        gamelib.debug_write('Configuring your custom algo strategy...')
        self.config = config
        global WALL, SUPPORT, TURRET, SCOUT, DEMOLISHER, INTERCEPTOR, MP, SP, SELF, ENEMY, SCOUT_RANGE, DEMOLISHER_RANGE, INTERCEPTOR_RANGE
        WALL = config["unitInformation"][0]["shorthand"]
        SUPPORT = config["unitInformation"][1]["shorthand"]
        TURRET = config["unitInformation"][2]["shorthand"]
        SCOUT = config["unitInformation"][3]["shorthand"]
        DEMOLISHER = config["unitInformation"][4]["shorthand"]
        INTERCEPTOR = config["unitInformation"][5]["shorthand"]
        MP = 1
        SP = 0
        ENEMY = 1
        SELF = 0
        SCOUT_RANGE = config["unitInformation"][3]["attackRange"]
        DEMOLISHER_RANGE = config["unitInformation"][4]["attackRange"]
        INTERCEPTOR_RANGE = config["unitInformation"][5]["attackRange"]
        # This is a good place to do initial setup
        self.scored_on_locations = []
        self.turn_enemy_attack = []
        self.turn_enemy_attack_pre = []
        self.turn_enemy_attack_stats = {}
        self.enemy_scout_spawn_locations = {}
        self.enemy_demolisher_spawn_locations = {}
        self.enemy_interceptor_spawn_locations = {}
        self.kamikaze_ready = False

        self.enemy_mobile_points = []

        self.last_attack = ["NONE"]
        self.attack_flag = 0
        # attack_flag: 0 no attack, 1 prep attack, 2 attacked finished
        self.attack_side = 0
        #attack_side: 0 left, 1 right
        self.attack_strat = 0
        #attack_strat 0 short 1 long


    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
        game_state.suppress_warnings(True)  # Comment or remove this line to enable warnings.

        self.starter_strategy(game_state)

        game_state.submit_turn()

    """
    NOTE: All the methods after this point are part of the sample starter-algo
    strategy and can safely be replaced for your custom algo.
    """

    def starter_strategy(self, game_state):
        """
        For defense we will use a spread out layout and some interceptors early on.
        We will place turrets near locations the opponent managed to score on.
        For offense we will use long range demolishers if they place stationary units near the enemy's front.
        If there are no stationary units to attack in the front, we will send Scouts to try and score quickly.
        """
        # First, place basic defenses
        self.build_defences(game_state)

        # Now build reactive defenses based on where the enemy scored
        # self.build_reactive_defense(game_state)

        # If the turn is less than 5, stall with interceptors and wait to see enemy's base
        # if game_state.turn_number < 5:
        #     self.stall_with_interceptors(game_state)
        # else:
        # Now let's analyze the enemy base to see where their defenses are concentrated.
        # If they have many units in the front we can build a line for our demolishers to attack them at long range.
        # if self.detect_enemy_unit(game_state, unit_type=None, valid_x=None, valid_y=[14, 15]) > 10:
        #     # self.demolisher_line_strategy(game_state)
        # else:
        # They don't have many units in the front so lets figure out their least defended area and send Scouts there.

        # Only spawn Scouts every other turn
        # Sending more at once is better since attacks can only hit a single scout at a time
        # if game_state.turn_number % 2 == 1:
        #     # To simplify we will just check sending them from back left and right
        #     scout_spawn_location_options = [[13, 0], [14, 0]]
        #     best_location = self.least_damage_spawn_location(game_state, scout_spawn_location_options)
        #     game_state.attempt_spawn(SCOUT, best_location, 1000)
        self.count_attack(game_state)
        self.time_enemy_attack(game_state)
        # if game_state.turn_number % 5 == 0:
        #     self.attack_walls(game_state)
        # if game_state.turn_number % 2 == 0:
        #     # random number > 0.4 attack with scout only, otherwise combination of demolisher and scout
        #     self.attack_focus(game_state)
        # self.calculate_brute_force(game_state)
        if self.attack_flag == 2:
            if self.attack_strat == 1:
                self.long_attack(game_state, self.attack_side)
            else:
                self.short_attack(game_state, self.attack_side)
            self.attack_flag = 0

        if game_state.get_resource(MP, SELF) >= 13:
            gamelib.debug_write("OUR MP IS CURRENTLY", game_state.get_resource(MP, SELF))
            self.attack_flag = 1

        if self.attack_flag == 1:
            rng = random.random()
            if rng >= 0.5:
                self.attack_side = self.attack_prep_short(game_state)
                self.attack_strat = 0
            else:
                self.attack_side = self.attack_prep_long(game_state)
                self.attack_strat = 1
            self.attack_flag = 2



        # Lastly, if we have spare SP, let's build some supports and corner walls
        # corner_reinforcement_loc = [[1, 12], [2, 12], [25, 12], [26, 12]]
        # game_state.attempt_spawn(WALL, corner_reinforcement_loc)
        if game_state.get_resource(SP, SELF) > 20:
            right = [[20, 8], [20, 9], [19, 7], [18, 6], [17, 5], [21, 10], [22, 10], [23, 10]]
            left = [[7, 9], [7, 8], [8, 7], [9, 6], [10, 5], [4, 10], [5, 10], [6, 10]]
            game_state.attempt_upgrade(right + left)

    """--------------------PREDICTIVE PATHING--------------------"""

    def __in_kamikaze_range(self, game_state, enemy_location, suicide_location):
        """
        `enemy_location`: list of len 2 representing coordinates of hypothetical enemy unit
        `suicide_location`: list of len2 representing coordinates of kamikaze suicide location
        """
        return game_state.game_map.distance_between_locations(enemy_location, suicide_location) <= 9

    def __can_kill_kamikaze(self, game_state, enemy_location, enemy_range, kamikaze_location):
        """
        `enemy_location`: list of len 2 representing coordinates of hypothetical enemy unit
        `enemy_range`: range of enemy unit
        `suicide_location`: list of len2 representing coordinates of kamikaze suicide location
        """
        return game_state.game_map.distance_between_locations(enemy_location, kamikaze_location) <= enemy_range 

    def kamikaze_ideal_steps(self, game_state, starting_location):
        # Short
        LshortSuicide = [2, 11]
        RshortSuicide = [25, 11]
        # Even and Odd Long
        lSuicide = [5, 9] # {"even": [5, 9], "odd": [6,9]}
        rSuicide = [22, 9] # {"even": [22, 9], "odd": [21,9]}

        if not starting_location:
            return {"left": 7, "right": 7}
        # Stores results for number of steps interceptor should take on both sides.
        idealSteps = {}
        # Check if starting spawn point is in range of short attack
        if self.__in_kamikaze_range(game_state, starting_location, LshortSuicide):
            idealSteps["left"] = 1
        if self.__in_kamikaze_range(game_state, starting_location, RshortSuicide):
            idealSteps["right"] = 1
        # If both are in then we can spawn immediately
        if "left" in idealSteps and "right" in idealSteps:
            return idealSteps

        path = game_state.find_path_to_edge(starting_location)
        
        for step, point in enumerate(path):
            if "left" not in idealSteps and self.__in_kamikaze_range(game_state, point, lSuicide): 
                idealSteps["left"] = step // 4 + 1
                                
            if "right" not in idealSteps and self.__in_kamikaze_range(game_state,point, rSuicide):
                idealSteps["right"] = (step + 1) // 4 + 1

            if "left" in idealSteps and "right" in idealSteps:
                return idealSteps

        if "left" not in idealSteps:
            idealSteps["left"] = 0
        if "right" not in idealSteps:
            idealSteps["right"] = 0

        return idealSteps

    """------------------------------------------------ATTACK------------------------------------------------"""

    # def attack_walls(self, game_state):
    #     # left = [[21, 10], [20, 10], [19, 10], [18, 9]]
    #     # right = [[9, 9], [6, 10], [7, 10], [8, 10]]
    #     game_state.attempt_remove(left + right)

    def attack_focus(self, game_state):
        """
        This function focuses on attacking one side of the opponent board
        """
        left_side_units, right_side_units = self.weaker_side(game_state, unit_type=None)
        # simple justificaiton of which side is weaker base on the number of units, should be replaced with more detailed enemy defence unit distribution estimation
        if right_side_units > left_side_units:
            # rnd = random.random()
            # if rnd > 0.4:
            #     scout_spawn_location_options_bottom = [[14, 0]]
            #     game_state.attempt_spawn(SCOUT, scout_spawn_location_options_bottom, 50)
            # else:
            # wall_flex_loc = [[21, 10], [20, 10], [19, 10], [18, 9]]
            # , [22, 11], [23, 11], [24, 12]]
            # game_state.attempt_spawn(WALL, wall_flex_loc)

            demolisher_spawn_location_options_top = [[14, 0]]
            game_state.attempt_spawn(DEMOLISHER, demolisher_spawn_location_options_top, 5)

            scout_spawn_location_options_top = [[25, 11]]
            game_state.attempt_spawn(SCOUT, scout_spawn_location_options_top, 5)

            scout_spawn_location_options_bottom = [[15, 1]]
            game_state.attempt_spawn(SCOUT, scout_spawn_location_options_bottom, 50)

        else:
            # rnd = random.random()
            # if rnd > 0.4:
            #     scout_spawn_location_options_bottom = [[13, 0]]
            #     game_state.attempt_spawn(SCOUT, scout_spawn_location_options_bottom, 50)
            # else:
            # wall_flex_loc = [ [6, 10], [7, 10]]
            # game_state.attempt_spawn(WALL, wall_flex_loc)

            demolisher_spawn_location_options_bottom = [[13, 0]]
            game_state.attempt_spawn(DEMOLISHER, demolisher_spawn_location_options_bottom, 5)

            scout_spawn_location_options_bottom = [[12, 1]]
            game_state.attempt_spawn(SCOUT, scout_spawn_location_options_bottom, 5)

            scout_spawn_location_options_top = [[3, 10]]
            game_state.attempt_spawn(SCOUT, scout_spawn_location_options_top, 50)

        # else:
        #     rnd2 = random.random()
        #     if rnd2 >= 0.5:
        #         demolisher_spawn_location_options_top = [[14, 0]]
        #         game_state.attempt_spawn(DEMOLISHER, demolisher_spawn_location_options_top, 5)

        #         scout_spawn_location_options_bottom = [[15, 1]]
        #         game_state.attempt_spawn(SCOUT, scout_spawn_location_options_bottom, 50)

        #     else:
        #         demolisher_spawn_location_options_top = [[13, 0]]
        #         game_state.attempt_spawn(DEMOLISHER, demolisher_spawn_location_options_top, 5)

        #         scout_spawn_location_options_bottom = [[12, 1]]
        #         game_state.attempt_spawn(SCOUT, scout_spawn_location_options_bottom, 50)

    def attack_prep_short(self, game_state):
        left_side_units, right_side_units = self.weaker_side(game_state, unit_type=None)
        if left_side_units > right_side_units:
            attack_side = 1
            game_state.attempt_remove([[26, 13], [27, 13], [17, 4], [23, 9], [24, 11], [25, 11]])

        else:
            attack_side = 0
            game_state.attempt_remove([[0, 13], [1, 13], [10, 4], [4, 9], [3, 11], [2, 12]])

        return attack_side
    def attack_prep_long(self, game_state):
        left_side_units, right_side_units = self.weaker_side(game_state, unit_type=None)
        if left_side_units > right_side_units:
            attack_side = 1
            game_state.attempt_remove([[26, 13], [27, 13], [17, 4], [23, 9], [24, 11], [25, 11], [10, 4]])
            # game_state.attempt_spawn(WALL, [,])
        else:
            attack_side = 0
            game_state.attempt_remove([[0, 13], [1, 13], [10, 4], [4, 9], [3, 11], [2, 12],[17 ,4]])
        game_state.attempt_spawn(WALL, [[22, 12],[5, 12]])
        return attack_side

    def long_attack(self, game_state, attack_side):
        # attack side 1 right, 0 left
        if attack_side == 1:
            first_wave = [7, 6]
            game_state.attempt_spawn(SCOUT, first_wave, 8)
            sec_wave = [6, 7]
            # game_state.attempt_spawn(DEMOLISHER, sec_wave, 2)
            game_state.attempt_spawn(SCOUT, sec_wave, 100)

        else:
            first_wave = [20, 6]
            game_state.attempt_spawn(SCOUT, first_wave, 8)
            sec_wave = [21, 7]
            # game_state.attempt_spawn(DEMOLISHER, start_location, 2)
            game_state.attempt_spawn(SCOUT, sec_wave, 100)

    def short_attack(self, game_state, attack_side):
        # attack side 1 right, 0 left
        if attack_side:
            first_wave = [13, 0]
            game_state.attempt_spawn(SCOUT, first_wave, 8)
            sec_wave = [12, 1]
            # game_state.attempt_spawn(DEMOLISHER, sec_wave, 2)
            game_state.attempt_spawn(SCOUT, sec_wave, 100)

        else:
            first_wave = [14, 0]
            game_state.attempt_spawn(SCOUT, first_wave, 8)
            sec_wave = [15, 1]
            # game_state.attempt_spawn(DEMOLISHER, start_location, 2)
            game_state.attempt_spawn(SCOUT, sec_wave, 100)

    def calculate_brute_force(self, game_state):
        # Check weaker side, to decide which edge to target
        left_side_units, right_side_units = self.weaker_side(game_state, unit_type=None)
        if left_side_units > right_side_units:
            opposite_edge = game_state.game_map.TOP_RIGHT
            start_location = [13, 0]
        else:
            opposite_edge = game_state.game_map.TOP_LEFT
            start_location = [14, 0]
        # modify turret coverage to show how many turrets, will be passed through
        # calculate how much damage it is expected to take
        damage = self.damage_on_path(game_state, start_location)
        turrets = self.turrets_on_path(game_state, start_location)
        last_attack = self.last_attack[-1]
        if last_attack == "FULL BREACH":
            # Follow up attack, trying to deal as much damage with scouts as possible
            game_state.attempt_spawn(INTERCEPTOR, start_location, 1)
            game_state.attempt_spawn(SCOUT, start_location, 50)
            self.last_attack.append("FOLLOW-UP")
        else:
            # calculate best attack with current MP
            random_attack_token = random.choice([0, 1, 2])
            if game_state.turn_number % 3 == random_attack_token:
                if (game_state.get_resource(MP, SELF) >= 15):
                    game_state.attempt_spawn(DEMOLISHER, start_location, 5)
                    game_state.attempt_spawn(SCOUT, start_location, 50)
                    game_state.attempt_spawn(DEMOLISHER, start_location, 50)
                    self.last_attack.append("FULL BREACH")

                elif (game_state.get_resource(MP, SELF) >= 10):
                    # Need to be able to tank
                    if turrets == 1:
                        game_state.attempt_spawn(SCOUT, start_location, 15)
                        self.last_attack.append("SCOUT")


                elif (game_state.get_resource(MP, SELF) < 10):
                    game_state.attempt_spawn(DEMOLISHER, start_location, 1)
                    self.last_attack.append("POKE")

    """------------------------------------------------DEFENCE------------------------------------------------"""


    """--------------------BUILD DEFENCE--------------------"""       

    """ KAMIKAZE STUFF """             

    def __fast_kamikaze_defence(self, game_state, left=True, right=True):
        # 2 SP
        leftWalls = [[2,12],[3,11]] if left else [[0,0]]
        rightWalls = [[25,12],[24,11]] if right else [[0,0]]
        game_state.attempt_spawn(WALL, leftWalls + rightWalls)
        game_state.attempt_remove(leftWalls + rightWalls)
        # 2 MP
        leftSpawn = [[2,11]] if left else [[0,0]]
        rightSpawn = [[25,11]] if right else [[0,0]]
        game_state.attempt_spawn(INTERCEPTOR, leftSpawn + rightSpawn)

    def __slow_kamikaze_defence(self, game_state, left=True, right=True, steps=9):

        leftWalls = [[4, 9], [10, 4]] if left else [[0,0]]
        rightWalls = [[23, 9], [17, 4]] if right else [[0,0]]
        game_state.attempt_spawn(WALL, leftWalls + rightWalls)

        if steps >= 9:
            leftSpawn = [[9,4]] if left else [[0,0]]
            rightSpawn = [[18,4]] if left else [[0,0]]
            game_state.attempt_spawn(INTERCEPTOR, leftSpawn + rightSpawn)
        elif steps >=7:
            leftSpawn = [[8,5]] if left else [[0,0]]
            rightSpawn = [[19,5]] if left else [[0,0]]
            game_state.attempt_spawn(INTERCEPTOR, leftSpawn + rightSpawn)
        elif steps >=5:
            leftSpawn = [[7,6]] if left else [[0,0]]
            rightSpawn = [[20,6]] if left else [[0,0]]
            game_state.attempt_spawn(INTERCEPTOR, leftSpawn + rightSpawn)
        elif steps >= 3:
            leftSpawn = [[6,7]] if left else [[0,0]]
            rightSpawn = [[21,7]] if left else [[0,0]]
            game_state.attempt_spawn(INTERCEPTOR, leftSpawn + rightSpawn)

        extraLeft = [[6,9]] if left else [[0,0]]
        extraRight = [[21,9]] if right else [[0,0]]

        if steps % 2 == 0:
            game_state.attempt_spawn(WALL, extraLeft + extraRight)
        else:
            game_state.attempt_remove(extraLeft + extraRight)

    
    """ 
    If we are choosing to defend we need:
        LONG DEFENCE:
            DEFAULT: (Interceptor takes 9 steps to detonate)
                1 SP + 1 MP for each side
                So left + right defence we need 2 SP and 2 MP
            EVEN NUMBER OF STEPS:
                IF we decide to take even number of steps we need 0.5 extra MP for each side. So we need 3 SP and 2MP for left and right defence in total
    """
    def spawn_kamikaze(self, game_state):
        mpThreshold = math.floor(self.enemy_mobile(game_state))
        gamelib.debug_write("MP Threshold is", mpThreshold)
        gamelib.debug_write("Attack flag", self.attack_flag)
        if game_state.get_resource(MP, SELF) >= mpThreshold and self.attack_flag != 2 and game_state.turn_number>=2:        
            scouts = self.most_spawn_location(SCOUT)
            demos = self.most_spawn_location(DEMOLISHER)
            scouts_lr = self.kamikaze_ideal_steps(game_state, scouts)
            demos_lr = self.kamikaze_ideal_steps(game_state, demos)

            # Need 2SP and 2MP
            if scouts_lr["left"] == 1 or demos_lr["left"] == 1:
                self.__fast_kamikaze_defence(game_state, True, False)
            if scouts_lr["right"] == 1 or demos_lr["right"] == 1:
                self.__fast_kamikaze_defence(game_state, False, True)
                        
            if scouts_lr["left"] > 1 and demos_lr["left"] > 1:
                self.__slow_kamikaze_defence(game_state, True, False, demos_lr["left"])
            elif scouts_lr["left"] > 1:
                self.__slow_kamikaze_defence(game_state, True, False, scouts_lr["left"])
            elif demos_lr["left"] > 1:
                self.__slow_kamikaze_defence(game_state, True, False, demos_lr["left"])
                
            if scouts_lr["right"] > 1 and demos_lr["right"] > 1:
                self.__slow_kamikaze_defence(game_state, False, True, demos_lr["right"])
            elif scouts_lr["left"] > 1:
                self.__slow_kamikaze_defence(game_state, False, True, scouts_lr["right"])
            elif demos_lr["left"] > 1:
                self.__slow_kamikaze_defence(game_state, False, True, demos_lr["right"])


    # def spawn_kamikaze(self, game_state, left=[[8, 5]], right=[[19, 5]], left_num=1, right_num=1):
    #     """
    #     This function assumes that there are enough resources to spawn the amount given.
    #     Shall be handled by external function.
    #     """
    #     scouts = self.most_spawn_location(SCOUT)
    #     demos = self.most_spawn_location(DEMOLISHER)

    #     combined = left + right
    #     # scouts_lr = self.kamikaze_ideal_steps(game_state, scouts, [[7, 7], [20, 7]])
    #     # demos_lr = self.kamikaze_ideal_steps(game_state, demos, [[7, 7], [20, 7]])

    #     left_steps = max(scouts_lr["left"], demos_lr["left"])
    #     right_steps = max(scouts_lr["left"], demos_lr["left"])

    #     gamelib.debug_write("Left to take ", left_steps)
    #     gamelib.debug_write("Right to take ", right_steps)

    #     while left_num > 0 or right_num > 0:
    #         if left_num > 0:
    #             if left_steps % 2 == 1:
    #                 game_state.attempt_remove([[6, 8], [7, 8]])
    #                 if left_steps == 5:
    #                     game_state.attempt_spawn(INTERCEPTOR, left)
    #                 elif left_steps > 5:
    #                     game_state.attempt_spawn(INTERCEPTOR, [[9, 4]])
    #                 else:
    #                     game_state.attempt_spawn(INTERCEPTOR, [[7, 6]])
    #             else:
    #                 game_state.attempt_spawn(WALL, [[6, 8], [7, 8]])
    #                 if left_steps == 4:
    #                     game_state.attempt_spawn(INTERCEPTOR, left)
    #                 elif left_steps > 4:
    #                     game_state.attempt_spawn(INTERCEPTOR, [[9, 4]])
    #                 else:
    #                     game_state.attempt_spawn(INTERCEPTOR, [[7, 6]])
    #             left_num -= 1
    #         if right_num > 0:
    #             if right_steps % 2 == 1:
    #                 game_state.attempt_remove([[20, 8], [21, 8]])
    #                 if right_steps == 5:
    #                     game_state.attempt_spawn(INTERCEPTOR, right)
    #                 elif right_steps > 5:
    #                     game_state.attempt_spawn(INTERCEPTOR, [[18, 4]])
    #                 else:
    #                     game_state.attempt_spawn(INTERCEPTOR, [[20, 6]])
    #             else:
    #                 game_state.attempt_spawn(WALL, [[20, 8], [21, 8]])
    #                 if right_steps == 4:
    #                     game_state.attempt_spawn(INTERCEPTOR, right)
    #                 elif right_steps > 4:
    #                     game_state.attempt_spawn(INTERCEPTOR, [[18, 4]])
    #                 else:
    #                     game_state.attempt_spawn(INTERCEPTOR, [[20, 6]])
    #             right_num -= 1

    """ Others """

    def rebuild_low_health_defence(self, game_state, locations, exceptions=[], unit_type=None, health_threshold=65):
        """
        Rebuild corner defence (defence that should exist every turn) if their health is less than
        `health_threshold`.
        Also will build walls if they don't exist there so original attempt_spawn() in build_defences() function
        is removed.
        ----------
        Parameters
        ----------
        `exceptions`: a list of lists containing coordinates of key walls that should not be rebuilt this round, default is []
        `health_threshold`: Value is from 0-100
        """
        for location in game_state.game_map:
            if (location in locations) and (location not in exceptions):
                # if wall currently exists at the location, check its health
                if game_state.contains_stationary_unit(location):
                    for unit in game_state.game_map[location]:
                        if unit.player_index == 0 and (unit.unit_type == unit_type) and (
                                unit.health <= (health_threshold / 100) * unit.max_health):
                            game_state.attempt_remove(location)
                # if wall doesn't exist in the location
                else:
                    game_state.attempt_spawn(unit_type, location)

    def initial_build(self, game_state):
        # Place turrets that attack enemy units
        turret_locations = [[3, 12], [5, 10], [22, 10], [24, 12]]
        # attempt_spawn will try to spawn units if we have resources, and will check if a blocking unit is already there
        game_state.attempt_spawn(TURRET, turret_locations)
        # Place walls in front of turrets to soak up damage for them
        turret_defense_walls = [[2, 13], [3, 13], [4, 13], [6, 11], [6, 10], [21, 10], [21, 11], [23, 13], [24, 13],
                                [25, 13], [1, 13], [0, 13], [27, 13], [26, 13]]
        V_shape_walls = [[7, 9], [7, 8], [8, 7], [9, 6], [10, 5], [11, 4], [12, 3], [13, 2], [14, 2], [15, 3], [16, 4],
                         [17, 5], [18, 6], [19, 7], [20, 8], [20, 9]]
        game_state.attempt_spawn(WALL, turret_defense_walls + V_shape_walls)

        upgrades = [[4, 13], [23, 13]]
        game_state.attempt_upgrade(upgrades)

    def rebuild_tower_defenses(self, game_state):
        turret_locations = [[3, 12], [5, 10], [22, 10], [24, 12]]
        game_state.attempt_spawn(TURRET, turret_locations)
        turret_defense_walls = [[2, 13], [3, 13], [4, 13], [6, 11], [6, 10], [21, 10], [21, 11], [23, 13], [24, 13],
                                [25, 13]]
        if self.attack_flag == 0:
            self.rebuild_low_health_defence(game_state,[[27, 13], [26, 13], [1, 13], [0, 13]],[],WALL,25)
        self.rebuild_low_health_defence(game_state, turret_defense_walls, [], unit_type=WALL, health_threshold=25)

    def rebuild_v_wall(self, game_state):
        V_shape_walls = [[7, 9], [7, 8], [8, 7], [9, 6], [10, 5], [11, 4], [12, 3], [13, 2], [14, 2], [15, 3], [16, 4],
                         [17, 5], [18, 6], [19, 7], [20, 8], [20, 9]]
        self.rebuild_low_health_defence(game_state, V_shape_walls, [], unit_type=WALL, health_threshold=25)

    def rebuild(self, game_state):
        self.rebuild_tower_defenses(game_state)
        self.rebuild_v_wall(game_state)

    def upgrade(self, game_state):
        upgrades = [[4, 13], [23, 13], [6, 11], [21, 11], [24, 13], [3, 13], [6, 10], [21, 10], [1, 13], [0, 13],
                    [27, 13], [26, 13]]
        game_state.attempt_upgrade(upgrades)

    def extend_defense(self, game_state):
        # If health is in a good position, build supports
        
        if game_state.turn_number > 7 and game_state.my_health >= 15:
            row_1_support_locations = [[11, 7], [12, 7], [13, 7], [14, 7], [15, 7], [16, 7]]
            row_2_support_locations = [[11, 6], [12, 6], [13, 6], [14, 6], [15, 6], [16, 6]]
            row_3_support_locations = [[11, 5], [12, 5], [13, 5], [14, 5], [15, 5], [16, 5]]
            game_state.attempt_spawn(SUPPORT, row_1_support_locations)
            game_state.attempt_upgrade(row_1_support_locations)
            game_state.attempt_spawn(SUPPORT, row_2_support_locations)
            game_state.attempt_upgrade(row_2_support_locations)
            game_state.attempt_spawn(SUPPORT, row_3_support_locations)
            game_state.attempt_upgrade(row_3_support_locations)

        # If health is low, build more turrets to boost defense
        elif game_state.turn_number > 7 and game_state.my_health <= 15:
            build_turrets_locations = []
            build_walls_locations = []

            for location in self.scored_on_locations:
                if location in [[0, 13], [1, 12], [2, 11], [3, 10], [4, 9], [5, 8], [6, 7], [7, 6]]:
                    build_turrets_locations.append([7, 10])
                    build_turrets_locations.append([7, 11])
                    build_walls_locations.append([7, 12])
                    build_walls_locations.append([8, 11])
                    game_state.attempt_spawn(TURRET, build_turrets_locations)
                    game_state.attempt_spawn(WALL, build_walls_locations)
                    game_state.attempt_upgrade(build_turrets_locations)
                elif location in [[27, 13], [26, 12], [25, 11], [24, 10], [23, 9], [22, 8], [21, 7], [20, 6]]:
                    build_turrets_locations.append([20, 10])
                    build_turrets_locations.append([20, 11])
                    build_walls_locations.append([20, 12])
                    build_walls_locations.append([19, 11])
                    game_state.attempt_spawn(TURRET, build_turrets_locations)
                    game_state.attempt_spawn(WALL, build_walls_locations)
                    game_state.attempt_upgrade(build_turrets_locations)
                else:
                    build_turrets_locations.append([location[0], location[1]+3])
                    build_walls_locations.append([location[0], location[1]+4])
                    game_state.attempt_spawn(TURRET, build_turrets_locations)
                    game_state.attempt_spawn(WALL, build_walls_locations)
                    game_state.attempt_upgrade(build_turrets_locations)

    def build_defences(self, game_state):
        """
        Build basic defenses using hardcoded locations.
        Remember to defend corners and avoid placing units in the front where enemy demolishers can attack them.
        """

        # Turn 1 - Build Initial Defense
        if game_state.turn_number == 0:
            self.initial_build(game_state)

        # All other turns
        else:
            self.rebuild(game_state)
            self.spawn_kamikaze(game_state)
            self.upgrade(game_state)
            self.extend_defense(game_state)

    # def build_reactive_defense(self, game_state):
    #     """
    #     This function builds reactive defenses based on where the enemy scored on us from.
    #     We can track where the opponent scored by looking at events in action frames
    #     as shown in the on_action_frame function
    #     """
    #     for location in self.scored_on_locations:
    #         # Build turret one space above so that it doesn't block our own edge spawn locations
    #         build_location = [location[0], location[1]+1]
    #         game_state.attempt_spawn(TURRET, build_location)

    def stall_with_interceptors(self, game_state):
        """
        Send out interceptors at random locations to defend our base from enemy moving units.
        """
        # We can spawn moving units on our edges so a list of all our edge locations
        friendly_edges = game_state.game_map.get_edge_locations(
            game_state.game_map.BOTTOM_LEFT) + game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_RIGHT)

        # Remove locations that are blocked by our own structures
        # since we can't deploy units there.
        deploy_locations = self.filter_blocked_locations(friendly_edges, game_state)

        # While we have remaining MP to spend lets send out interceptors randomly.
        while game_state.get_resource(MP) >= game_state.type_cost(INTERCEPTOR)[MP] and len(deploy_locations) > 0:
            # Choose a random deploy location.
            deploy_index = random.randint(0, len(deploy_locations) - 1)
            deploy_location = deploy_locations[deploy_index]

            game_state.attempt_spawn(INTERCEPTOR, deploy_location)
            """
            We don't have to remove the location since multiple mobile 
            units can occupy the same space.
            """

    # def demolisher_line_strategy(self, game_state):
    #     """
    #     Build a line of the cheapest stationary unit so our demolisher can attack from long range.
    #     """
    #     # First let's figure out the cheapest unit
    #     # We could just check the game rules, but this demonstrates how to use the GameUnit class
    #     stationary_units = [WALL, TURRET, SUPPORT]
    #     cheapest_unit = WALL
    #     for unit in stationary_units:
    #         unit_class = gamelib.GameUnit(unit, game_state.config)
    #         if unit_class.cost[game_state.MP] < gamelib.GameUnit(cheapest_unit, game_state.config).cost[game_state.MP]:
    #             cheapest_unit = unit

    #     # Now let's build out a line of stationary units. This will prevent our demolisher from running into the enemy base.
    #     # Instead they will stay at the perfect distance to attack the front two rows of the enemy base.
    #     for x in range(27, 5, -1):
    #         game_state.attempt_spawn(cheapest_unit, [x, 11])

    #     # Now spawn demolishers next to the line
    #     # By asking attempt_spawn to spawn 1000 units, it will essentially spawn as many as we have resources for
    #     game_state.attempt_spawn(DEMOLISHER, [24, 10], 1000)

    """------------------------------------------------INTEL------------------------------------------------"""

    def least_damage_spawn_location(self, game_state, location_options):
        """
        This function will help us guess which location is the safest to spawn moving units from.
        It gets the path the unit will take then checks locations on that path to
        estimate the path's damage risk.
        """
        damages = []
        # Get the damage estimate each path will take
        for location in location_options:
            path = game_state.find_path_to_edge(location)
            damage = 0
            for path_location in path:
                # Get number of enemy turrets that can attack each location and multiply by turret damage
                damage += len(game_state.get_attackers(path_location, 0)) * gamelib.GameUnit(TURRET,
                                                                                             game_state.config).damage_i
            damages.append(damage)

        # Now just return the location that takes the least damage
        return location_options[damages.index(min(damages))]

    def detect_enemy_unit(self, game_state, unit_type=None, valid_x=None, valid_y=None):
        total_units = 0
        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.player_index == 1 and (unit_type is None or unit.unit_type == unit_type) and (
                            valid_x is None or location[0] in valid_x) and (valid_y is None or location[1] in valid_y):
                        total_units += 1
        return total_units

    def filter_blocked_locations(self, locations, game_state):
        filtered = []
        for location in locations:
            if not game_state.contains_stationary_unit(location):
                filtered.append(location)
        return filtered

    def weaker_side(self, game_state, unit_type=None):
        left_side_units = 0
        left = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]

        right_side_units = 0
        right = [14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]

        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.player_index == 1 and (left is None or location[0] in left):
                        if unit.unit_type == WALL:
                            left_side_units += 1
                        elif unit.unit_type == TURRET:
                            left_side_units += 12
                        elif unit.unit_type == SUPPORT:
                            left_side_units += 1
                    elif unit.player_index == 1 and (right is None or location[0] in right):
                        if unit.unit_type == WALL:
                            left_side_units += 1
                        elif unit.unit_type == TURRET:
                            left_side_units += 12
                        elif unit.unit_type == SUPPORT:
                            left_side_units += 1

        return left_side_units, right_side_units

    def find_enemy_turrets(self, game_state, unit_type=None, valid_x=None, valid_y=None):
        total_turrets = 0
        turret_locations = []
        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location) == "TURRET":
                for unit in game_state.game_map[location]:
                    if unit.player_index == 1 and (unit_type is None or unit.unit_type == unit_type) and (
                            valid_x is None or location[0] in valid_x) and (valid_y is None or location[1] in valid_y):
                        total_turrets += 1
                        turret_locations.append(location)
        return total_turrets, turret_locations

    def damage_on_path(self, game_state, location):
        damage = 0
        path = game_state.find_path_to_edge(location)
        gamelib.debug_write(path)
        if path:
            for path_location in path:
                damage += len(game_state.get_attackers(path_location, 0)) * gamelib.GameUnit(TURRET,
                                                                                             game_state.config).damage_i

        return damage

    def turrets_on_path(self, game_state, location):
        turrets = 0
        path = game_state.find_path_to_edge(location)
        if path:
            for path_location in path:
                turrets += len(game_state.get_attackers(path_location, 0))

        return turrets

    def filter_blocked_locations(self, locations, game_state):
        filtered = []
        for location in locations:
            if not game_state.contains_stationary_unit(location):
                filtered.append(location)
        return filtered

    def enemy_mobile(self, game_state):
        # return the minimum enemy mobile points that we need to be awared of
        self.enemy_mobile_points.append(game_state.get_resource(1, 1))
        gamelib.debug_write(self.enemy_mobile_points)
        min_mobile_point = 0
        difference = []
        for i in range(1, len(self.enemy_mobile_points)):
            if self.enemy_mobile_points[i - 1] + 5 - self.enemy_mobile_points[i] >= 10:
                difference.append(self.enemy_mobile_points[i - 1] + 5 - self.enemy_mobile_points[i])
        gamelib.debug_write(difference)
        if difference:
            if min(difference) >= 10:
                return min(difference)
        else:
            return 10

    def count_attack(self, game_state):
        # if not self.enemy_scout_spawn_locations or not self.enemy_demolisher_spawn_locations:
        scout_count = copy.copy(self.enemy_scout_spawn_locations)
        demolisher_count = copy.copy(self.enemy_demolisher_spawn_locations)
        # interceptor_count = copy.copy(self.enemy_interceptor_spawn_locations)
        self.turn_enemy_attack = [scout_count,
                                  demolisher_count]
        gamelib.debug_write(
            "-------------------------------------------------------------------------------------------")
        gamelib.debug_write(self.turn_enemy_attack)
        gamelib.debug_write(self.turn_enemy_attack_pre)
        gamelib.debug_write(self.turn_enemy_attack_stats)
        gamelib.debug_write(
            "-------------------------------------------------------------------------------------------")
        if game_state.turn_number >= 1:
            # self.turn_enemy_attack_stats[game_state.turn_number - 1] = 1

            if not self.turn_enemy_attack_pre:
                self.turn_enemy_attack_pre = self.turn_enemy_attack
                self.turn_enemy_attack_stats[game_state.turn_number - 1] = 1
            elif self.turn_enemy_attack_pre != self.turn_enemy_attack:
                self.turn_enemy_attack_pre = self.turn_enemy_attack
                self.turn_enemy_attack_stats[game_state.turn_number - 1] = 1
            else:
                self.turn_enemy_attack_stats[game_state.turn_number - 1] = 0

    def time_enemy_attack(self, game_state):
        # collect the turns when enemy attacked
        out = []
        for key, value in self.turn_enemy_attack_stats.items():
            if value == 1 and key not in out:
                out.append(key)
        # for i in range(10):

        gamelib.debug_write(out)
        return out

    # This function takes unit_type as parameter (SCOUT, INTERCEPTOR, DEMOLISHER), and return the most spawned coordinate in [x, y] format
    def most_spawn_location(self, unit_type=None):
        if unit_type == SCOUT:
            if self.enemy_scout_spawn_locations:
                coordinate = max(self.enemy_scout_spawn_locations, key=self.enemy_scout_spawn_locations.get)
                coordinate = list(coordinate)
                return coordinate
        elif unit_type == DEMOLISHER:
            if self.enemy_demolisher_spawn_locations:
                coordinate = max(self.enemy_demolisher_spawn_locations, key=self.enemy_demolisher_spawn_locations.get)
                coordinate = list(coordinate)
                return coordinate
        elif unit_type == INTERCEPTOR:
            if self.enemy_interceptor_spawn_locations:
                coordinate = max(self.enemy_interceptor_spawn_locations, key=self.enemy_interceptor_spawn_locations.get)
                coordinate = list(coordinate)
                return coordinate

        return None

    def on_action_frame(self, turn_string):
        """
        This is the action frame of the game. This function could be called 
        hundreds of times per turn and could slow the algo down so avoid putting slow code here.
        Processing the action frames is complicated so we only suggest it if you have time and experience.
        Full doc on format of a game frame at in json-docs.html in the root of the Starterkit.
        """
        # Let's record at what position we get scored on
        state = json.loads(turn_string)
        events = state["events"]
        breaches = events["breach"]
        for breach in breaches:
            location = breach[0]
            unit_owner_self = True if breach[4] == 1 else False
            # When parsing the frame data directly, 
            # 1 is integer for yourself, 2 is opponent (StarterKit code uses 0, 1 as player_index instead)
            if not unit_owner_self:
                gamelib.debug_write("Got scored on at: {}".format(location))
                self.scored_on_locations.append(location)
                gamelib.debug_write("All locations: {}".format(self.scored_on_locations))
        spawns = events["spawn"]
        for spawn in spawns:
            location = tuple(spawn[0])
            unit_owner_self = True if spawn[3] == 1 else False

            if not unit_owner_self:
                if spawn[1] == 3:
                    # if game_state.turn_number in self.turn_enemy_attack:
                    #     self.turn_enemy_attack[game_state.turn_number] = [3, location, 1]
                    # else:
                    #     self.turn_enemy_attack[game_state.turn_number][2] += 1

                    if location in self.enemy_scout_spawn_locations:
                        self.enemy_scout_spawn_locations[location] += 1
                        # self.most_spawn_location(unit_type=SCOUT)
                    else:
                        self.enemy_scout_spawn_locations[location] = 1
                    # gamelib.debug_write("Enemy spawned scout")
                    # gamelib.debug_write("At: {}".format(location))
                    # gamelib.debug_write("Scouts: {}".format(self.enemy_scout_spawn_locations))
                elif spawn[1] == 4:
                    if location in self.enemy_demolisher_spawn_locations:
                        self.enemy_demolisher_spawn_locations[location] += 1
                    else:
                        self.enemy_demolisher_spawn_locations[location] = 1
                    # gamelib.debug_write("Enemy spawned demolisher")
                    # gamelib.debug_write("At: {}".format(location))
                    # gamelib.debug_write("Demolisher: {}".format(self.enemy_demolisher_spawn_locations))
                elif spawn[1] == 5:  # 3, 4, 5 stands for scout, demolisher, interceptor
                    if location in self.enemy_interceptor_spawn_locations:
                        self.enemy_interceptor_spawn_locations[location] += 1
                    else:
                        self.enemy_interceptor_spawn_locations[location] = 1
                    # gamelib.debug_write("Enemy spawned interceptor")
                    # gamelib.debug_write("At: {}".format(location))
                    # gamelib.debug_write("Interceptor: {}".format(self.enemy_interceptor_spawn_locations))


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
