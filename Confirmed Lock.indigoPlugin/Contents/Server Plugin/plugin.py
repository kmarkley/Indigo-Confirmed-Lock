#! /usr/bin/env python
# -*- coding: utf-8 -*-
###############################################################################
# http://www.indigodomo.com

import indigo
import threading
import Queue
import time

# Note the "indigo" module is automatically imported and made available inside
# our global name space by the host process.

###############################################################################
# globals

k_commonTrueStates = ('true', 'on', 'open', 'up', 'yes', 'active', 'locked', '1')
k_pesterPlug  = indigo.server.getPlugin("com.perceptiveautomation.indigoplugin.timersandpesters")

################################################################################
class Plugin(indigo.PluginBase):
    #-------------------------------------------------------------------------------
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

    def __del__(self):
        indigo.PluginBase.__del__(self)

    #-------------------------------------------------------------------------------
    # Start, Stop and Config changes
    #-------------------------------------------------------------------------------
    def startup(self):
        self.debug = self.pluginPrefs.get("showDebugInfo",False)
        self.logger.debug("startup")
        if self.debug:
            self.logger.debug("Debug logging enabled")
        self.deviceDict = dict()
        indigo.devices.subscribeToChanges()

    #-------------------------------------------------------------------------------
    def shutdown(self):
        self.logger.debug("shutdown")
        self.pluginPrefs["showDebugInfo"] = self.debug

    #-------------------------------------------------------------------------------
    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        self.logger.debug("closedPrefsConfigUi")
        if not userCancelled:
            self.debug = valuesDict.get("showDebugInfo",False)
            if self.debug:
                self.logger.debug("Debug logging enabled")

    #-------------------------------------------------------------------------------
    def validatePrefsConfigUi(self, valuesDict):
        self.logger.debug("validatePrefsConfigUi")
        errorsDict = indigo.Dict()

        if len(errorsDict) > 0:
            return (False, valuesDict, errorsDict)
        return (True, valuesDict)

    #-------------------------------------------------------------------------------
    # Device Methods
    #-------------------------------------------------------------------------------
    def deviceStartComm(self, dev):
        self.logger.debug("deviceStartComm: "+dev.name)
        if dev.version != self.pluginVersion:
            self.updateDeviceVersion(dev)
        if dev.deviceTypeId == 'confirmedLock':
            self.deviceDict[dev.id] = ConfirmedLock(dev, self)
            self.deviceDict[dev.id].start()
        elif dev.deviceTypeId == 'dummyLock':
            self.deviceDict[dev.id] = DummyLock(dev, self)

    #-------------------------------------------------------------------------------
    def deviceStopComm(self, dev):
        self.logger.debug("deviceStopComm: "+dev.name)
        if dev.id in self.deviceDict:
            if dev.deviceTypeId == 'confirmedLock':
                self.deviceDict[dev.id].cancel()
            del self.deviceDict[dev.id]

    ########################################
    def validateDeviceConfigUi(self, valuesDict, typeId, devId, runtime=False):
        self.logger.debug("validateDeviceConfigUi: " + typeId)
        errorsDict = indigo.Dict()

        if typeId == 'confirmedLock':
            if not zint(valuesDict.get('lockDevice',0)):
                errorsDict['lockDevice'] = "Required"
            if valuesDict.get('doorSensorBool', False):
                if not zint(valuesDict.get('doorSensorDevice', 0)):
                    errorsDict['doorSensorDevice'] = "Required"
                if not valuesDict.get('doorSensorState', ''):
                    errorsDict['doorSensorState'] = "Required"
            if valuesDict.get('deadboltSensorBool', False):
                if not zint(valuesDict.get('deadboltSensorDevice', 0)):
                    errorsDict['deadboltSensorDevice'] = "Required"
                if not valuesDict.get('deadboltSensorState', ''):
                    errorsDict['ddeadboltSensorState'] = "Required"
            if valuesDict.get('actionBool', False):
                if not zint(valuesDict.get('actionGroup', 0)):
                    errorsDict['actionGroup'] = "Required"
                if zint(valuesDict.get('pesterCycles', '')):
                    if not zint(valuesDict.get('pesterDelay',0)):
                        errorsDict['pesterDelay'] = "Required positive integer"
            if valuesDict.get('messageBool', False):
                if not zint(valuesDict.get('messageVariable', 0)):
                    errorsDict['messageVariable'] = "Required"
                if not valuesDict.get('messageText', ''):
                    errorsDict['messageText'] = "Required"

        if len(errorsDict) > 0:
            return (False, valuesDict, errorsDict)
        return (True, valuesDict)

    ########################################
    def updateDeviceVersion(self, dev):
        theProps = dev.pluginProps
        # update states
        dev.stateListOrDisplayStateIdChanged()
        # check for props

        # push to server
        theProps["version"] = self.pluginVersion
        dev.replacePluginPropsOnServer(theProps)

    #-------------------------------------------------------------------------------
    # Device updated
    #-------------------------------------------------------------------------------
    def deviceUpdated(self, oldDev, newDev):

        # device belongs to plugin
        if newDev.pluginId == self.pluginId or oldDev.pluginId == self.pluginId:
            indigo.PluginBase.deviceUpdated(self, oldDev, newDev)

        for devId, dev in self.deviceDict.items():
            dev.deviceUpdated(oldDev, newDev)

    #-------------------------------------------------------------------------------
    # Action Methods
    #-------------------------------------------------------------------------------
    def actionControlDevice(self, action, dev):
        lockDev = self.deviceDict[dev.id]
        if action.deviceAction in (indigo.kDeviceAction.Lock,indigo.kDeviceAction.TurnOn):
            lockDev.lock()
        elif action.deviceAction in (indigo.kDeviceAction.Unlock,indigo.kDeviceAction.TurnOff):
            lockDev.unlock()
        elif action.deviceAction == indigo.kDeviceAction.Toggle:
            [lockDev.lock(),lockDev.unlock()][dev.onState]
        elif action.deviceAction == indigo.kDeviceAction.RequestStatus:
            self.logger.info('"{0}" status update'.format(dev.name))
            lockDev.updateStatus()
        else:
            self.logger.debug('"{0}" {1} request ignored'.format(dev.name, str(action.deviceAction)))


    ########################################
    # Menu Methods
    ########################################
    def toggleDebug(self):
        if self.debug:
            self.logger.debug("Debug logging disabled")
            self.debug = False
        else:
            self.debug = True
            self.logger.debug("Debug logging enabled")

    #-------------------------------------------------------------------------------
    # Menu Callbacks
    #-------------------------------------------------------------------------------
    def getLockDeviceList(self, filter="", valuesDict=None, typeId="", targetId=0):
        devList = []
        for dev in indigo.devices.iter(filter='props.IsLockSubType'):
            if dev.deviceTypeId != 'confirmedLock':
                devList.append((dev.id, dev.name))
        return devList

    #-------------------------------------------------------------------------------
    def getStateList(self, filter=None, valuesDict=dict(), typeId='', targetId=0):
        stateList = list()
        devId = zint(valuesDict.get(filter,''))
        if devId:
            for state in indigo.devices[devId].states:
                stateList.append((state,state))
        return stateList

    #-------------------------------------------------------------------------------
    def loadStates(self, valuesDict=None, typeId='', targetId=0):
        pass

################################################################################
# Classes
################################################################################
class ConfirmedLock(threading.Thread):

    #-------------------------------------------------------------------------------
    def __init__(self, instance, plugin):
        super(ConfirmedLock, self).__init__()
        self.daemon     = True
        self.cancelled  = False
        self.queue      = Queue.Queue()

        self.plugin     = plugin
        self.logger     = plugin.logger
        self.sleep      = plugin.sleep
        self.substitute = plugin.substitute
        self.device     = instance
        self.confirmed  = False

        self.lockDev    = indigo.devices[int(instance.pluginProps['lockDevice'])]

        self.attempts   = zint(instance.pluginProps.get('attemptsCount', 3))
        self.waitTime   = zint(instance.pluginProps.get('attemptsDelay', 10))

        self.doorBool   = instance.pluginProps.get('doorSensorBool',False)
        self.doorState  = instance.pluginProps.get('doorSensorState','onOffState')
        self.doorLogic  = zool(instance.pluginProps.get('doorSensorLogic',False))
        try:
            self.doorDev    = indigo.devices[int(instance.pluginProps['doorSensorDevice'])]
        except:
            self.doorDev    = None

        self.deadBool   = instance.pluginProps.get('deadboltSensorBool',False)
        self.deadState  = instance.pluginProps.get('deadboltSensorState','onOffState')
        self.deadLogic  = zool(instance.pluginProps.get('deadboltSensorLogic',False))
        self.deadDelay  = zint(instance.pluginProps.get('deadboltSensorDelay',2))
        try:
            self.deadDev    = indigo.devices[int(instance.pluginProps['deadboltSensorDevice'])]
        except:
            self.deadDev    = None

        self.actionBool     = zool(instance.pluginProps.get('actionBool',False))
        self.actionGroup    = zint(instance.pluginProps.get('actionGroup',0))

        self.pesterBool     = zool(instance.pluginProps.get('pesterCycles',False))
        self.pesterProps    = {
            'name'                      :   'ConfirmedLock-{}-Pester'.format(self.device.id),
            'cycles'                    :   zint(instance.pluginProps.get('pesterCycles',0)),
            'seconds'                   :   zint(instance.pluginProps.get('pesterDelay',60)),
            'actionGroupId'             :   zint(instance.pluginProps.get('actionGroup',0)),
            'executeFinalActionGroup'   :   zool(instance.pluginProps.get('pesterFinal',0)),
            'finalActionGroupId'        :   zint(instance.pluginProps.get('pesterFinal',0)),
            }
        self.pesterActive   = False

        self.messageBool    = instance.pluginProps.get('messageBool',False)
        self.messageVar     = zint(instance.pluginProps.get('messageVariable',0))
        self.messageText    = instance.pluginProps.get('messageText','')

        self.updateStatus()

    #-------------------------------------------------------------------------------
    def run(self):
        self.logger.debug('{}: thread started'.format(self.device.name))
        while not self.cancelled:
            try:
                task = self.queue.get(True,2)
                self.taskTime = time.time()
                self.setLockState(task)
                self.queue.task_done()
            except Queue.Empty:
                pass
            except Exception as e:
                self.logger.error('{}: thread error \n{}'.format(self.device.name, e))
        else:
            self.logger.debug('{}: thread cancelled'.format(self.device.name))

    #-------------------------------------------------------------------------------
    def cancel(self):
        """End this thread"""
        self.cancelled = True

    #-------------------------------------------------------------------------------
    def lock(self):
        self.queue.put(True)

    #-------------------------------------------------------------------------------
    def unlock(self):
        self.queue.put(False)

    #-------------------------------------------------------------------------------
    def setLockState(self, lockState):
        if lockState:
            for attempt in range(self.attempts):
                attemptTime = time.time()
                self.logger.debug('Locking device "{}" (attempt {})'.format(self.device.name, attempt+1))
                if not self.doorBool or zool(self.doorDev.states[self.doorState]) == self.doorLogic:
                    if not self.lockDev.onState:
                        indigo.device.lock(self.lockDev)
                    if self.deadBool and not zool(self.deadDev.states[self.deadState]) == self.deadLogic:
                        self.sleep(self.deadDelay)
                self.updateStatus()
                if self.confirmed:
                    self.logger.info('Device "{}" locked'.format(self.device.name))
                    if self.messageBool:
                        indigo.variable.updateValue(self.messageVar,'')
                    if self.pesterActive:
                        k_pesterPlug.executeAction('cancelPester', props=self.pesterProps)
                        self.pesterActive = False
                    break
                self.sleep(self.waitTime - (time.time() - attemptTime))
            else:
                self.logger.error('Failed to lock "{}" after {} attempts'.format(self.device.name, self.attempts))
                if self.messageBool:
                    indigo.variable.updateValue(self.messageVar,self.substitute(self.messageText))
                if self.actionBool:
                    indigo.actionGroup.execute(self.actionGroup)
                if self.pesterBool:
                    k_pesterPlug.executeAction('createPester', props=self.pesterProps)
                    self.pesterActive = True
        else:
            self.logger.debug('Unlocking device "{}"'.format(self.device.name))
            indigo.device.unlock(self.lockDev)
            if self.deadBool:
                self.sleep(self.deadDelay)
            self.updateStatus()
            if not self.confirmed:
                self.logger.info('Device "{}" unlocked'.format(self.device.name))
                if self.messageBool:
                    indigo.variable.updateValue(self.messageVar,'')
                if self.pesterActive:
                    k_pesterPlug.executeAction('cancelPester', props=self.pesterProps)
                    self.pesterActive = False

    #-------------------------------------------------------------------------------
    def updateStatus(self):
        door_closed = deadbolt_engaged = True

        if self.doorBool:
            door_closed = zool(self.doorDev.states[self.doorState]) == self.doorLogic

        lock_locked = self.lockDev.onState

        if self.deadBool:
            deadbolt_engaged = zool(self.deadDev.states[self.deadState]) == self.deadLogic

        self.confirmed = door_closed and lock_locked and deadbolt_engaged

        if not door_closed:
            text_state = 'open'
        elif not lock_locked:
            text_state = 'unlocked'
        elif not deadbolt_engaged:
            text_state = 'unconfirmed'
        else:
            text_state = 'confirmed'

        newStates = [
            {'key':'onOffState',        'value':self.confirmed},
            {'key':'door_closed',       'value':door_closed},
            {'key':'lock_locked',       'value':lock_locked},
            {'key':'deadbolt_engaged',  'value':deadbolt_engaged},
            {'key':'state',             'value':text_state},
            ]
        self.device.updateStatesOnServer(newStates)

    #-------------------------------------------------------------------------------
    def deviceUpdated(self, oldDev, newDev):
        if newDev.id == self.device.id:
            self.device = newDev
        elif self.doorBool and newDev.id == self.doorDev.id:
            self.doorDev = newDev
            self.updateStatus()
        elif newDev.id == self.lockDev.id:
            self.lockDev = newDev
            self.updateStatus()
        elif self.deadBool and newDev.id == self.deadDev.id:
            self.deadDev = newDev
            self.updateStatus()

################################################################################
class DummyLock(object):

    #-------------------------------------------------------------------------------
    def __init__(self, instance, plugin):
        self.plugin = plugin
        self.logger = plugin.logger
        self.device = instance

    #-------------------------------------------------------------------------------
    def lock(self):
        self.device.updateStateOnServer('onOffState',True)

    #-------------------------------------------------------------------------------
    def unlock(self):
        self.device.updateStateOnServer('onOffState',False)

    #-------------------------------------------------------------------------------
    def updateStatus(self):
        pass

    #-------------------------------------------------------------------------------
    def deviceUpdated(self, oldDev, newDev):
        if newDev.id == self.device.id:
            self.device = newDev

################################################################################
# Utilities
################################################################################
def zint(value):
    try: return int(value)
    except: return 0

#-------------------------------------------------------------------------------
def zool(value):
    result = False
    if zint(value):
        result =  True
    elif isinstance(value, basestring):
        result = value.lower() in k_commonTrueStates
    return result
