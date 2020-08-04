"""Supervisor Controller Prototype v1
   Written by Robbie Goldman and Alfred Roberts
"""

from controller import Supervisor
import os
import random
import struct
import math
import datetime


# Create the instance of the supervisor class
supervisor = Supervisor()

# Get this supervisor node - so that it can be rest when game restarts
mainSupervisor = supervisor.getFromDef("MAINSUPERVISOR")

maxTimeMinute = 8
# Maximum time for a match
maxTime = maxTimeMinute * 60

DEFAULT_MAX_VELOCITY = 6.28


class Queue:
    def __init__(self):
        self.queue = []

    def enqueue(self, data):
        return self.queue.append(data)

    def dequeue(self):
        return self.queue.pop(0)

    def peek(self):
        return self.queue[0]

    def is_empty(self):
        return len(self.queue) == 0


class RobotHistory(Queue):
    def __init__(self):
        super().__init__()
        self.master_history = []

    def enqueue(self, data):
        self.update_master_history(data)
        if len(self.queue) > 8:
            self.dequeue()
        return self.queue.append(data)

    def update_master_history(self, data):
        time = int(maxTime - timeElapsed)
        #print(time)
        minute = str(datetime.timedelta(seconds=time))[2:]
        #print(minute)
        record = [minute, data]
        self.master_history.append(record)


class Robot:
    '''Robot object to hold values whether its in a base or holding a human'''

    def __init__(self, node=None):
        '''Initialises the in a base, has a human loaded and score values'''

        self.wb_node = node

        try:
            self.wb_translationField = self.wb_node.getField('translation')
            self.wb_rotationField = self.wb_node.getField('rotation')
        except:
            pass


        self.inCheckpoint = True
        self.inSwamp = True

        self.history = RobotHistory()

        self._score = 0

        self._timeStopped = 0
        self._stopped = False
        self._stoppedTime = None

        self.message = []

        #TODO make first tile first checkpoint
        self.lastVisitedCheckPointPosition = []

        self.visitedCheckpoints = []

        self.startingTile = None

        self.inSimulation = True

        self.name = "NO_TEAM_NAME"

        #self.previousPosition = [None,None,None]

    @property
    def position(self) -> list:
        return self.wb_translationField.getSFVec3f()

    @position.setter
    def position(self, pos: list) -> None:
        self.wb_translationField.setSFVec3f(pos)

    @property
    def rotation(self) -> list:
        return self.wb_rotationField.getSFRotation()

    @rotation.setter
    def rotation(self, pos: list) -> None:
        self.wb_rotationField.setSFRotation(pos)

    def setMaxVelocity(self, vel: float) -> None:
        self.wb_node.getField('max_velocity').setSFFloat(vel)

    def _isStopped(self) -> bool:
        vel = self.wb_node.getVelocity()
        robotStopped = abs(vel[0]) < 0.01 and abs(vel[1]) < 0.01 and abs(vel[2]) < 0.01
        return robotStopped

    def timeStopped(self) -> float:
        self._stopped = self._isStopped()

        # if it isn't stopped yet
        if self._stoppedTime == None:
            if self._stopped:
                # get time the robot stopped
                self._stoppedTime = supervisor.getTime()
        else:
            # if its stopped
            if self._stopped:
                # get current time
                currentTime = supervisor.getTime()
                # calculate the time the robot stopped
                self._timeStopped = currentTime - self._stoppedTime
            else:
                # if it's no longer stopped, reset variables
                self._stoppedTime = None
                self._timeStopped = 0

        return self._timeStopped

    def increaseScore(self, score: int) -> None:
        if self._score + score < 0:
            self._score = 0
        else:
            self._score += score

    def getScore(self) -> int:
        return self._score
    
    def get_log_str(self):
        history = self.history.master_history
        log_str = ""
        for event in history:
            log_str += str(event[0]) + " " + event[1] + "\n"
            
        return log_str


class Human():
    '''Human object holding the boundaries'''

    def __init__(self, node, ap: int, vtype: str, score: int):
        '''Initialises the radius and position of the human'''

        self.wb_node = node

        self.wb_translationField = self.wb_node.getField('translation')

        self.wb_rotationField = self.wb_node.getField('rotation')

        self.wb_typeField = self.wb_node.getField('type')
        self.wb_foundField = self.wb_node.getField('found')

        self.arrayPosition = ap
        self.scoreWorth = score
        self.radius = 0.15
        self._victim_type = vtype

        self.simple_victim_type = self.get_simple_victim_type()

    @property
    def position(self) -> list:
        return self.wb_translationField.getSFVec3f()

    @position.setter
    def position(self, pos: list) -> None:
        self.wb_translationField.setSFVec3f(pos)

    @property
    def rotation(self) -> list:
        return self.wb_rotationField.getSFRotation()

    @rotation.setter
    def rotation(self, pos: list) -> None:
        self.wb_rotationField.setSFRotation(pos)

    @property
    def victim_type(self) -> list:
        return self.wb_typeField.getSFString()

    @victim_type.setter
    def victim_type(self, v_type: str):
        self.wb_typeField.setSFString(v_type)

    @property
    def identified(self) -> list:
        return self.wb_foundField.getSFBool()

    @identified.setter
    def identified(self, idfy: int):
        self.wb_foundField.setSFBool(idfy)

    def get_simple_victim_type(self):
        if self._victim_type == 'harmed':
            return 'H'
        elif self._victim_type == 'unharmed':
            return 'U'
        elif self._victim_type == 'stable':
            return 'S'
        elif self._victim_type == 'heat': # Temperature victim
            return 'T'
        else:
            return self._victim_type

    def getType(self) -> int:
        '''Set type of human (adult or child) through object size'''
        # Get human size
        humanSize = self.wb_node.getField("scale").getSFVec3f()

        if humanSize[1] == 0.5:
            return 2
        else:
            return 1

    def checkPosition(self, pos: list, min_dist: float) -> bool:
        '''Check if a position is near an object, based on the min_dist value'''
        # Get distance from the object to the passed position using manhattan distance for speed
        # TODO Check if we want to use euclidian or manhattan distance -- currently manhattan
        distance = math.sqrt(((self.position[0] - pos[0])**2) + ((self.position[2] - pos[2])**2))
        return distance <= min_dist

    def onSameSide(self, pos: list) -> bool:
        #get side its pointing at

        #0 1 0 -pi/2 -> X axis
        #0 1 0 pi/2 -> -X axis
        #0 1 0 pi -> Z axis
        #0 1 0 0 -> -Z axis

        rot = self.rotation[3]
        rot = round(rot, 2)

        if rot == -1.57:
            #X axis
            robot_x = pos[0]
            if robot_x > self.position[0]:
                return True
        elif rot == 1.57:
            #-X axis
            robot_x = pos[0]
            if robot_x < self.position[0]:
                return True
        elif rot == 3.14:
            #Z axis
            robot_z = pos[2]
            if robot_z > self.position[2]:
                return True
        elif rot == 0:
            #-Z axis
            robot_z = pos[2]
            if robot_z < self.position[2]:
                return True

        return False
        



class Tile():
    '''Tile object holding the boundaries'''

    def __init__(self, min: list, max: list, center: list):
        '''Initialize the maximum and minimum corners for the tile'''
        self.min = min
        self.max = max
        self.center = center

    def checkPosition(self, pos: list) -> bool:
        '''Check if a position is in this checkpoint'''
        # If the x position is within the bounds
        if pos[0] >= self.min[0] and pos[0] <= self.max[0]:
            # if the z position is within the bounds
            if pos[2] >= self.min[1] and pos[2] <= self.max[1]:
                # It is in this checkpoint
                return True

        # It is not in this checkpoint
        return False


class Checkpoint(Tile):
    '''Checkpoint object holding the boundaries'''

    def __init__(self, min: list, max: list, center=None):
        super().__init__(min, max, center)


class Swamp(Tile):
    '''Swamp object holding the boundaries'''

    def __init__(self, min: list, max: list, center=None):
        super().__init__(min, max, center)


class StartTile(Tile):
    '''StartTile object holding the boundaries'''

    def __init__(self, min: list, max: list, center=None):
        super().__init__(min, max, center)


def getPath(number: int) -> str:
    '''Get the path to the correct controller'''
    # The current path to this python file
    filePath = os.path.dirname(os.path.abspath(__file__))

    filePath = filePath.replace('\\', '/')

    # Split into parts on \
    pathParts = filePath.split("/")

    filePath = ""
    # Add all parts back together
    for part in pathParts:
        # Except the last one
        if part != pathParts[-1]:
            # Concatenate with / not \ (prevents issues with escape characters)
            filePath = filePath + part + "/"

    # Controller number part added
    if number == 0:
        filePath = filePath + "robot0Controller/robot0Controller.py"
    elif number == 1:
        filePath = filePath + "robot1Controller/robot1Controller.py"
    else:
        # Returns none if id was not valid
        filePath = None

    return filePath


def resetControllerFile(number: int) -> None:
    '''Open the controller at the file location and blanks it'''
    filePath = getPath(number)

    if filePath != None:
        controllerFile = open(filePath, "w")
        controllerFile.close()


def createController(number: int, fileData: list) -> list:
    '''Opens the controller at the file location and writes the data to it'''
    filePath = getPath(number)

    if filePath == None:
        return None, None

    controllerFile = open(filePath, "w")
    controllerFile.write(fileData)
    controllerFile.close()

    # If there is a name in the file
    if "RobotName:" in fileData:
        # Find the name
        name = fileData[fileData.index("RobotName:") + 10:]
        name = name.split("\n")[0]
        # Return data with a name
        return name, number

    # Return data without a name
    return None, number


def assignController(num: int, name: str) -> None:
    '''Send message to robot window to say that controller has loaded and with what name'''
    if name == None:
        name = "None"
    else:
        name = name[:-1]
    if num == 0:
        supervisor.wwiSendText("loaded0," + name)
    if num == 1:
        supervisor.wwiSendText("loaded1," + name)


def resetController(num: int) -> None:
    '''Send message to robot window to say that controller has been unloaded'''
    if num == 0:
        resetControllerFile(0)
        supervisor.wwiSendText("unloaded0")
    if num == 1:
        resetControllerFile(1)
        supervisor.wwiSendText("unloaded1")


def updateHistory():
    supervisor.wwiSendText(
        "historyUpdate" + "," + ",".join(robot0Obj.history.queue) + ":" + ",".join(robot1Obj.history.queue))


def getHumans():
    #print('yeet')
    #camera = supervisor.getFromDef('CAMERA')
    # Iterate for each human
    for i in range(numberOfHumans):
        # Get each human from children field in the human root node HUMANGROUP
        human = humanNodes.getMFNode(i)
        
        #human.setVisibility(camera, False)


        victimType = human.getField('type').getSFString()
        scoreWorth = human.getField('scoreWorth').getSFInt32()
        #print(victimType)
        #print(scoreWorth)

        # Create Human Object from human position
        humanObj = Human(human, i, victimType, scoreWorth)
        humans.append(humanObj)


def resetVictimsTextures():
    # Iterate for each victim
    for i in range(numberOfHumans):
        humans[i].identified = False


def relocate(robotObj):
    relocatePosition = robotObj.lastVisitedCheckPointPosition

    robotObj.position = [relocatePosition[0], -0.0751, relocatePosition[2]]
    robotObj.rotation = [0,1,0,0]

    robotObj.history.enqueue("Lack of Progress - 5")
    robotObj.history.enqueue("Relocating to checkpoint")
    robotObj.increaseScore(-5)
    updateHistory()

def robot_quit(robotObj, num, manualExit):
    if robotObj.inSimulation:
        robotObj.wb_node.remove()
        robotObj.inSimulation = False
        supervisor.wwiSendText("robotNotInSimulation"+str(num))
        if manualExit:
            robotObj.history.enqueue("Manual Exit")
        else:
            robotObj.history.enqueue("Successful Exit")


def add_robot(num):
    global robot0, robot1
    if int(num) == 0:
        if robot0 == None:
            filePath = os.path.dirname(os.path.abspath(__file__))
            filePath = filePath.replace('\\', '/')

            root = supervisor.getRoot()
            root_children_field = root.getField('children')
            root_children_field.importMFNode(12,filePath + '/../../nodes/robot0.wbo')
            robot0 = supervisor.getFromDef("ROBOT0")

            supervisor.wwiSendText("robotInSimulation0")

    elif int(num) == 1:
        if robot1 == None:
            filePath = os.path.dirname(os.path.abspath(__file__))
            filePath = filePath.replace('\\', '/')

            root = supervisor.getRoot()
            root_children_field = root.getField('children')
            root_children_field.importMFNode(13,filePath + '/../../nodes/robot1.wbo')
            robot1 = supervisor.getFromDef("ROBOT1")

            supervisor.wwiSendText("robotInSimulation1")

def create_log_str():
    r0_str = robot0Obj.get_log_str()
    r1_str = robot1Obj.get_log_str()
    
    log_str = ""
    log_str += "GAME_DURATION: "+str(maxTimeMinute)+":00\n"
    log_str += "ROBOT_0_SCORE: "+str(robot0Obj.getScore())+"\n"
    log_str += "\n"
    log_str += "ROBOT_0: "+str(robot0Obj.name)+"\n"
    log_str += r0_str
    log_str += "\n"
    
    return log_str

def write_log():
    log_str = create_log_str()
    filePath = os.path.dirname(os.path.abspath(__file__))
    filePath = filePath.replace('\\', '/')
    filePath = filePath + "/../../logs/"
    
    file_date = datetime.datetime.now()
    logFileName = file_date.strftime("log %m-%d-%y %H,%M,%S")
    
    filePath += logFileName + ".txt"

    try:
        logsFile = open(filePath, "w")
        logsFile.write(log_str)
        logsFile.close()
    except:
        print("Couldn't write log file, no log directory ./game/logs")
# Get the output from the object placement supervisor
# objectPlacementOutput = supervisor.getFromDef("OBJECTPLACER").getField("customData")

# Empty list to contain checkpoints
checkpoints = []
# Empty list to contain swamps
swamps = []
# Global empty list to contain human objects
humans = []

# Boolean value stating whether or not humans have been placed in the map
humansLoaded = False
# Get group node containing humans
humanGroup = supervisor.getFromDef('HUMANGROUP')
humanNodes = humanGroup.getField("children")
# Get number of humans in map
numberOfHumans = humanNodes.getCount()

# activity0 = supervisor.getFromDef('ACT0')
# activity0_mat = supervisor.getFromDef('ACT0MAT')
# activity0_matobj = ActivityBlock(activity0_mat.getField("translation").getSFVec3f(),activity0_mat,None)
# activity0obj = ActivityBlock(activity0.getField("translation").getSFVec3f(),activity0,activity0_matobj)


# Iterate for each checkpoint
checkpointBounds = supervisor.getFromDef('CHECKPOINTBOUNDS').getField('children')
numberOfCheckpoints = int(checkpointBounds.getCount())

for i in range(numberOfCheckpoints):
    # Get the checkpoint minimum node and translation
    checkpointMin = supervisor.getFromDef("checkpoint" + str(i) + "min")
    minPos = checkpointMin.getField("translation")
    # Get maximum node and translation
    checkpointMax = supervisor.getFromDef("checkpoint" + str(i) + "max")
    maxPos = checkpointMax.getField("translation")
    # Get the vector positions
    minPos = minPos.getSFVec3f()
    maxPos = maxPos.getSFVec3f()

    centerPos = [(maxPos[0]+minPos[0])/2,maxPos[1],(maxPos[2]+minPos[2])/2]
    # Create a checkpoint object using the min and max (x,z)
    checkpointObj = Checkpoint([minPos[0], minPos[2]], [maxPos[0], maxPos[2]], centerPos)
    checkpoints.append(checkpointObj)

numberOfSwamps = supervisor.getFromDef('SWAMPBOUNDS').getField('children').getCount()

for i in range(numberOfSwamps):
    # Get the swamp minimum node and translation
    swampMin = supervisor.getFromDef("swamp" + str(i) + "min")
    minPos = swampMin.getField("translation")
    # Get maximum node and translation
    swampMax = supervisor.getFromDef("swamp" + str(i) + "max")
    maxPos = swampMax.getField("translation")
    # Get the vector positions
    minPos = minPos.getSFVec3f()
    maxPos = maxPos.getSFVec3f()

    centerPos = [(maxPos[0]+minPos[0])/2,maxPos[1],(maxPos[2]+minPos[2])/2]
    # Create a swamp object using the min and max (x,z)
    swampObj = Checkpoint([minPos[0], minPos[2]], [maxPos[0], maxPos[2]], centerPos)
    swamps.append(swampObj)

getHumans()

# Not currently running the match
currentlyRunning = False
previousRunState = False

# The game has not yet started
gameStarted = False

# Get the robot nodes by their DEF names
robot0 = supervisor.getFromDef("ROBOT0")
#robot1 = supervisor.getFromDef("ROBOT1")

add_robot(0)
#add_robot(1)

# Init both robots as objects to hold their info
robot0Obj = Robot(robot0)
robot1Obj = Robot()
robot1Obj.inSimulation = False

# Both robots start in bases
# robot0InCheckpoint = True
# robot1InCheckpoint = True

# The simulation is running
simulationRunning = True
finished = False

# Reset the controllers
resetControllerFile(0)
#resetControllerFile(1)

# Starting scores
# score0 = 0
# score1 = 0

# How long the game has been running for
timeElapsed = 0
lastTime = -1

# Send message to robot window to perform setup
supervisor.wwiSendText("startup")

# For checking the first update with the game running
first = True

receiver = supervisor.getReceiver('receiver')
receiver.enable(32)

# Get the starting tile minimum node and translation
starting_PointMin = supervisor.getFromDef("start0min")
starting_minPos = starting_PointMin.getField("translation")

# Get maximum node and translation
starting_PointMax = supervisor.getFromDef("start0max")
starting_maxPos = starting_PointMax.getField("translation")

# Get the vector positons
starting_minPos = starting_minPos.getSFVec3f()
starting_maxPos = starting_maxPos.getSFVec3f()
starting_centerPos = [(starting_maxPos[0]+starting_minPos[0])/2,starting_maxPos[1],(starting_maxPos[2]+starting_minPos[2])/2]

startingTileObj = StartTile([starting_minPos[0], starting_minPos[2]], [starting_maxPos[0], starting_maxPos[2]], starting_centerPos)

robot0Obj.startingTile = startingTileObj
robot0Obj.lastVisitedCheckPointPosition = startingTileObj.center
#print(startingTileObj.center)
robot0Obj.visitedCheckpoints.append(startingTileObj.center)

# #----------------

# # Get the starting tile minimum node and translation
# robot1_startingPointMin = supervisor.getFromDef("start1min")
# robot1_minPos = robot1_startingPointMin.getField("translation")

# # Get maximum node and translation
# robot1_startingPointMax = supervisor.getFromDef("start1max")
# robot1_maxPos = robot1_startingPointMax.getField("translation")

# robot1_startingPoint = supervisor.getFromDef("start1")
# robot1_centerPos = robot1_startingPoint.getField("translation")

# # Get the vector positons
# robot1_minPos = robot1_minPos.getSFVec3f()
# robot1_maxPos = robot1_maxPos.getSFVec3f()
# robot1_centerPos = robot1_centerPos.getSFVec3f()

# robot1Obj.startingTile = startingTileObj
# robot1Obj.lastVisitedCheckPointPosition = startingTileObj.center
# robot1Obj.visitedCheckpoints.append(startingTileObj.center)

robot0Obj.position = [startingTileObj.center[0] - 0.05, startingTileObj.center[1], startingTileObj.center[2]]
# robot1Obj.position = [startingTileObj.center[0] + 0.05, startingTileObj.center[1], startingTileObj.center[2]]

# Until the match ends (also while paused)
while simulationRunning:

    # The first frame of the game running only
    if first and currentlyRunning:
        # Restart both controllers
        robot0.restartController()
        #robot1.restartController()
        first = False

    r0 = False
    r1 = False

    # Test if the robots are in bases
    for checkpoint in checkpoints:
        if robot0Obj.inSimulation:
            if checkpoint.checkPosition(robot0Obj.position):
                r0 = True
                robot0Obj.lastVisitedCheckPointPosition = checkpoint.center

                alreadyVisited = False

                if len(robot0Obj.visitedCheckpoints) > 0:
                    for visitedCheckpoint in robot0Obj.visitedCheckpoints:
                        if visitedCheckpoint == checkpoint.center:
                            alreadyVisited = True

                if not alreadyVisited:
                    robot0Obj.visitedCheckpoints.append(checkpoint.center)
                    robot0Obj.increaseScore(10)
                    robot0Obj.history.enqueue("Found checkpoint  +10")
                    updateHistory()

        if robot1Obj.inSimulation:
            if checkpoint.checkPosition(robot1Obj.position):
                r1 = True
                robot1Obj.lastVisitedCheckPointPosition = checkpoint.center

                alreadyVisited = False

                if len(robot1Obj.visitedCheckpoints) > 0:
                    for visitedCheckpoint in robot1Obj.visitedCheckpoints:
                        if visitedCheckpoint == checkpoint.center:
                            alreadyVisited = True

                if not alreadyVisited:
                    robot1Obj.visitedCheckpoints.append(checkpoint.center)
                    robot1Obj.increaseScore(10)
                    robot1Obj.history.enqueue("Found checkpoint  +10")
                    updateHistory()

    # #Print when robot0 enters or exits a checkpoint
    if robot0Obj.inSimulation:
        if robot0Obj.inCheckpoint != r0:
            robot0Obj.inCheckpoint = r0
            if robot0Obj.inCheckpoint:
                print("Robot 0 entered a checkpoint")
            else:
                print("Robot 0 exited a checkpoint")

    if robot1Obj.inSimulation:
        # #Print when robot1 enters or exits a checkpoint
        if robot1Obj.inCheckpoint != r1:
            robot1Obj.inCheckpoint = r1
            if robot1Obj.inCheckpoint:
                print("Robot 1 entered a checkpoint")
            else:
                print("Robot 1 exited a checkpoint")

    r0s = False
    r1s = False

    # Check if the robots are in swamps
    for swamp in swamps:
        if robot0Obj.inSimulation:
            if swamp.checkPosition(robot0Obj.position):
                r0s = True

        if robot1Obj.inSimulation:
            if swamp.checkPosition(robot1Obj.position):
                r1s = True

    # #Print when robot0 enters or exits a checkpoint
    if robot0Obj.inSimulation:
        if robot0Obj.inSwamp != r0s:
            robot0Obj.inSwamp = r0s
            if robot0Obj.inSwamp:
                robot0Obj.setMaxVelocity(2)
                #print("Robot 0 entered a swamp")
                robot0Obj.history.enqueue("Entered swamp")
                updateHistory()
            else:
                robot0Obj.setMaxVelocity(DEFAULT_MAX_VELOCITY)
                #print("Robot 0 exited a swamp")
                #robot0Obj.history.enqueue("Exited swamp")
                #updateHistory()

    # #Print when robot1 enters or exits a checkpoint
    if robot1Obj.inSimulation:
        if robot1Obj.inSwamp != r1s:
            robot1Obj.inSwamp = r1s
            if robot1Obj.inSwamp:
                robot1Obj.setMaxVelocity(2)
                #print("Robot 1 entered a swamp")
                robot0Obj.history.enqueue("Entered swamp")
                updateHistory()
            else:
                robot1Obj.setMaxVelocity(DEFAULT_MAX_VELOCITY)
                #print("Robot 1 exited a swamp")
                #robot1Obj.history.enqueue("Exited swamp")
                #updateHistory()

    if receiver.getQueueLength() > 0:
        receivedData = receiver.getData()
        tup = struct.unpack('i i i c', receivedData)

        robotNumber = tup[0]
        x = tup[1]
        z = tup[2]

        estimated_victim_position = (x / 100, 0, z / 100)

        victimType = tup[3].decode("utf-8")

        if robotNumber == 0:
            if robot0Obj.inSimulation:
                #print('message updated')
                robot0Obj.message = [estimated_victim_position, victimType]
                #print(robot0Obj.messages.queue)
        else:
            if robot1Obj.inSimulation:
                robot1Obj.message = [estimated_victim_position, victimType]

        receiver.nextPacket()

    if robot0Obj.inSimulation:
        if robot0Obj.message != []:

            #print('peek', robot0Obj.messages.peek())
            r0_exitmessage = robot0Obj.message[1]
            #print(r0_exitmessage)

            if r0_exitmessage == 'E':

                robot0Obj.message = []

                if robot0Obj.startingTile.checkPosition(robot0Obj.position):
                    #print("Robot 0 Successful Exit")

                    updateHistory()
                    # TODO Exit robot 0
                    robot_quit(robot0Obj, 0, False)

                    robot0Obj.increaseScore(10)
                    robot0Obj.increaseScore(int(robot0Obj.getScore() * 0.1))

    if robot1Obj.inSimulation:
        if robot1Obj.message != []:

            #print('peek', robot1Obj.messages.peek())
            r1_exitmessage = robot1Obj.message[1]
            #print(r1_exitmessage)

            if r1_exitmessage == 'E':

                robot1Obj.message = []

                if robot1Obj.startingTile.checkPosition(robot1Obj.position):
                    #print("Robot 1 Successful Exit")


                    updateHistory()
                    # TODO Exit robot 1
                    robot_quit(robot1Obj, 1, False)

                    robot1Obj.increaseScore(10)
                    robot1Obj.increaseScore(int(robot1Obj.getScore() * 0.1))

    if robot0Obj.inSimulation:
        if robot0Obj.timeStopped() >= 3:

            if robot0Obj.message != []:

                #print('peek', robot0Obj.messages.peek())
                r0_est_vic_pos = robot0Obj.message[0]
                #print(r0_est_vic_pos)
                r0_est_vic_type = robot0Obj.message[1]
                #print(robot0Obj.message)
                robot0Obj.message = []

                for i, h in enumerate(humans):
                    if not h.identified:
                        if h.checkPosition(robot0Obj.position, 0.15):
                            if h.checkPosition(r0_est_vic_pos, 0.15):
                                    if h.onSameSide(robot0Obj.position):
        
                                        #print("Robot 0 Successful Victim Identification")

                                        pointsScored = h.scoreWorth

                                        if r0_est_vic_type.lower() == h.simple_victim_type.lower():
                                            robot0Obj.history.enqueue("Successful Victim Type Correct Bonus  + 10")
                                            pointsScored += 10

                                        robot0Obj.history.enqueue("Successful Victim Identification " + " +" + str(h.scoreWorth))
                                        robot0Obj.increaseScore(pointsScored)

                                        h.identified = True
                                        updateHistory()
                            else:
                                robot0Obj.history.enqueue("Misidentification of victim  - 5")
                                robot0Obj.increaseScore(-5)

                                updateHistory()

    if robot1Obj.inSimulation:
        if robot1Obj.timeStopped() >= 3:

            if robot1Obj.message != []:

                #print('peek', robot1Obj.messages.peek())
                r1_est_vic_pos = robot1Obj.message[0]
                r1_est_vic_type = robot1Obj.message[1]

                robot1Obj.message = []

                for i, h in enumerate(humans):
                    if not h.identified:
                        if h.checkPosition(robot1Obj.position, 0.15):
                            if h.checkPosition(r1_est_vic_pos, 0.15):
                                    if h.onSameSide(robot1Obj.position):
        
                                        #print("Robot 1 Successful Victim Identification")

                                        pointsScored = h.scoreWorth

                                        if r1_est_vic_type.lower() == h.simple_victim_type.lower():
                                            robot1Obj.history.enqueue("Successful Victim Type Correct Bonus  + 10")
                                            pointsScored += 10

                                        robot1Obj.history.enqueue("Successful Victim Identification " + " +" + str(h.scoreWorth))
                                        robot1Obj.increaseScore(pointsScored)

                                        h.identified = True
                                        updateHistory()

                            else:
                                robot1Obj.history.enqueue("Misidentification of victim  - 5")
                                robot1Obj.increaseScore(-5)

                                updateHistory()

    if robot0Obj.inSimulation:
        if robot0Obj.timeStopped() >= 20:
            relocate(robot0Obj)

            robot0Obj._timeStopped = 0
            robot0Obj._stopped = False
            robot0Obj._stoppedTime = None

    if robot1Obj.inSimulation:
        if robot1Obj.timeStopped() >= 20:
            
            relocate(robot1Obj)

            robot1Obj._timeStopped = 0
            robot1Obj._stopped = False
            robot1Obj._stoppedTime = None

    # If the running state changes
    if previousRunState != currentlyRunning:
        # Update the value and #print
        previousRunState = currentlyRunning
        #print("Run State:", currentlyRunning)

    # Get human positions if game started
    # if gameStarted and not humansLoaded:
    #    getHumans()
    #    humansLoaded = True

    # Get the message in from the robot window(if there is one)
    message = supervisor.wwiReceiveText()
    # If there is a message
    if message != "":
        # split into parts
        parts = message.split(",")
        # If there are parts
        if len(parts) > 0:
            if parts[0] == "run":
                # Start running the match
                currentlyRunning = True
                lastTime = supervisor.getTime()
                gameStarted = True
            if parts[0] == "pause":
                # Pause the match
                currentlyRunning = False
            if parts[0] == "reset":
                # Reset both controller files
                resetControllerFile(0)
                resetControllerFile(1)            
                resetVictimsTextures()
                
                # Reset the simulation
                supervisor.simulationReset()
                simulationRunning = False
                finished = True
                # Restart this supervisor
                mainSupervisor.restartController()

            if parts[0] == "robot0File":
                # Load the robot 0 controller
                if not gameStarted:
                    data = message.split(",", 1)
                    if len(data) > 1:
                        name, id = createController(0, data[1])
                        if name != None:
                            robot0Obj.name = name
                        assignController(id, name)
                else:
                    print("Please choose controllers before simulation starts.")
            if parts[0] == "robot1File":
                # Load the robot 1 controller
                if not gameStarted:
                    data = message.split(",", 1)
                    if len(data) > 1:
                        name, id = createController(1, data[1])
                        assignController(id, name)
                else:
                    print("Please choose controllers before simulation starts.")
            if parts[0] == "robot0Unload":
                # Unload the robot 0 controller
                if not gameStarted:
                    resetController(0)
            if parts[0] == "robot1Unload":
                # Unload the robot 1 controller
                if not gameStarted:
                    resetController(1)
            if parts[0] == 'relocate':
                data = message.split(",", 1)
                if len(data) > 1:
                    if int(data[1]) == 0:
                        relocate(robot0Obj)
                    elif int(data[1]) == 1:
                        relocate(robot1Obj)
                        
            if parts[0] == 'quit':
                data = message.split(",", 1)
                if len(data) > 1:
                    if int(data[1]) == 0:
                        if gameStarted:
                            robot_quit(robot0Obj, 0, True)
                    elif int(data[1]) == 1:
                        if gameStarted:
                            robot_quit(robot1Obj, 1, True)
                    updateHistory()

    # Send the update information to the robot window
    supervisor.wwiSendText(
        "update," + str(robot0Obj.getScore()) + "," + str(robot1Obj.getScore()) + "," + str(timeElapsed))

    # If the time is up
    if timeElapsed >= maxTime:
        finished = True
        supervisor.wwiSendText("ended")

    # If the match is running
    if currentlyRunning and not finished:
        # Get the time since the last frame
        frameTime = supervisor.getTime() - lastTime
        # Add to the elapsed time
        timeElapsed = timeElapsed + frameTime
        # Get the current time
        lastTime = supervisor.getTime()
        # Step the simulation on
        step = supervisor.step(32)
        # If the simulation is terminated or the time is up
        if step == -1:
            # Stop simulating
            simulationRunning = False
            finished = True
            
    if not simulationRunning and timeElapsed > 0:
        write_log()
        
