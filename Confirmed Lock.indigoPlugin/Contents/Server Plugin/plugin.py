#! /usr/bin/env python
# -*- coding: utf-8 -*-
###############################################################################
# http://www.indigodomo.com

import indigo
import threading
import Queue
import time
from ghpu import GitHubPluginUpdater

# Note the "indigo" module is automatically imported and made available inside
# our global name space by the host process.

###############################################################################
# globals

k_commonTrueStates = ('true', 'on', 'open', 'up', 'yes', 'active', 'locked', '1')
pesterPlugin  = indigo.server.getPlugin("com.perceptiveautomation.indigoplugin.timersandpesters")

kPluginUpdateCheckHours = 24

################################################################################
class Plugin(indigo.PluginBase):
    #-------------------------------------------------------------------------------
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        self.updater = GitHubPluginUpdater(self)

    def __del__(self):
        indigo.PluginBase.__del__(self)

    #-------------------------------------------------------------------------------
    # Start, Stop and Config changes
    #-------------------------------------------------------------------------------
    def startup(self):
        self.nextCheck = self.pluginPrefs.get('nextUpdateCheck',0)
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
        self.pluginPrefs['nextUpdateCheck'] = self.nextCheck

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
    def runConcurrentThread(self):
        try:
            while True:
                if time.time() > self.nextCheck:
                    self.checkForUpdates()
                self.sleep(600)
        except self.StopThread:
            pass    # Optionally catch the StopThread exception and do any needed cleanup.
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

    #-------------------------------------------------------------------------------
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

            valuesDict['address'] = zint(valuesDict.get('lockDevice',0))

        if len(errorsDict) > 0:
            return (False, valuesDict, errorsDict)
        return (True, valuesDict)

    #-------------------------------------------------------------------------------
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


    #-------------------------------------------------------------------------------
    # Menu Methods
    #-------------------------------------------------------------------------------
    def checkForUpdates(self):
        self.nextCheck = time.time() + (kPluginUpdateCheckHours*60*60)
        try:
            self.updater.checkForUpdate()
        except Exception as e:
            msg = 'Check for update error.  Next attempt in {} hours.'.format(kPluginUpdateCheckHours)
            if self.debug:
                self.logger.exception(msg)
            else:
                self.logger.error(msg)
                self.logger.debug(e)

    #-------------------------------------------------------------------------------
    def updatePlugin(self):
        self.updater.update()

    #-------------------------------------------------------------------------------
    def forceUpdate(self):
        self.updater.update(currentVersion='0.0.0')

    #-------------------------------------------------------------------------------
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

        self.boltBool   = instance.pluginProps.get('deadboltSensorBool',False)
        self.boltState  = instance.pluginProps.get('deadboltSensorState','onOffState')
        self.boltLogic  = zool(instance.pluginProps.get('deadboltSensorLogic',False))
        self.boltDelay  = zint(instance.pluginProps.get('deadboltSensorDelay',5))
        try:
            self.boltDev    = indigo.devices[int(instance.pluginProps['deadboltSensorDevice'])]
        except:
            self.boltDev    = None

        self.actionBool     = zool(instance.pluginProps.get('actionBool',False))
        self.actionGroup    = zint(instance.pluginProps.get('actionGroup',0))

        self.pesterBool     = zool(instance.pluginProps.get('pesterCycles',0))
        self.pesterProps    = {
            'name'                      :   'ConfirmedLock-{}'.format(self.device.id),
            'cycles'                    :   zint(instance.pluginProps.get('pesterCycles',0)),
            'seconds'                   :   zint(instance.pluginProps.get('pesterDelay',60)),
            'actionGroupId'             :   zint(instance.pluginProps.get('actionGroup',0)),
            'executeFinalActionGroup'   :   zool(instance.pluginProps.get('pesterFinal',0)),
            'finalActionGroupId'        :   zint(instance.pluginProps.get('pesterFinal',0)),
            }
        self.cancelProps    = {
            'name'                      :   self.pesterProps['name'],
            }

        self.messageBool    = instance.pluginProps.get('messageBool',False)
        self.messageVarId   = zint(instance.pluginProps.get('messageVariable',0))
        self.messageText    = instance.pluginProps.get('messageText','')

        self._action_success = instance.states.get('action_success',True)

        self.updateStatus()

    #-------------------------------------------------------------------------------
    # properties
    #-------------------------------------------------------------------------------
    @property
    def onState(self):
        return self.door_confirmed and self.lock_confirmed and self.bolt_confirmed

    @property
    def door_confirmed(self):
        if self.doorBool:
            return zool(self.doorDev.states[self.doorState]) == self.doorLogic
        else:
            return True

    @property
    def lock_confirmed(self):
        return self.lockDev.onState

    @property
    def bolt_confirmed(self):
        if self.boltBool:
            return zool(self.boltDev.states[self.boltState]) == self.boltLogic
        else:
            return True

    @property
    def text_state(self):
        if not self.door_confirmed:
            return 'open'
        elif not self.lock_confirmed:
            return 'unlocked'
        elif not self.bolt_confirmed:
            return 'unconfirmed'
        else:
            return 'confirmed'

    def action_success_get(self):
        return self._action_success
    def action_success_set(self, value):
        success = zool(value)
        if self.messageBool:
            indigo.variable.updateValue(self.messageVarId,[self.substitute(self.messageText),''][success])
        if self.actionBool and not success:
            indigo.actionGroup.execute(self.actionGroup)
        if self.pesterBool:
            if not success:
                pesterPlugin.executeAction('createPester', props=self.pesterProps)
            elif not self.action_success:
                pesterPlugin.executeAction('cancelPester', props=self.cancelProps)
        self._action_success = success
        self.updateStatus()
    action_success = property(action_success_get, action_success_set)

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
                msg = '{}: thread error \n{}'.format(self.device.name, e)
                if self.plugin.debug:
                    self.logger.exception(msg)
                else:
                    self.logger.error(msg)
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
    def setLockState(self, setState):
        for attempt in range(self.attempts):
            self.logger.debug('{} device "{}" (attempt {})'.format(['Unlocking','Locking'][setState], self.device.name, attempt+1))
            loopTime = time.time()

            if setState:
                # lock
                if not self.onState:
                    if self.door_confirmed:
                        indigo.device.lock(self.lockDev)

            else:
                # unlock
                if self.lock_confirmed:
                    indigo.device.unlock(self.lockDev)

            # wait for mechanical deadbolt
            self.sleep(self.boltDelay)

            # status change should be caught by deviceUpdated method on main thread
            if self.onState == setState:
                # success
                self.logger.info('"{}" {}locked'.format(self.device.name, ['un',''][self.onState]))
                self.action_success = True
                break

            else:
                # failed attempt
                self.logger.debug('"{}" state is "{}"'.format(self.device.name, self.text_state))
                # wait for next attempt
                self.sleep(self.waitTime - (time.time() - loopTime))

        else:
            # failed all attempts
            self.logger.error('Failed to {}lock "{}" after {} attempts'.format(['','un'][self.onState], self.device.name, self.attempts))
            self.action_success = False

    #-------------------------------------------------------------------------------
    def deviceUpdated(self, oldDev, newDev):
        if newDev.id == self.device.id:
            self.device = newDev
            return
        elif newDev.id == self.doorDev.id:
            self.doorDev = newDev
        elif newDev.id == self.lockDev.id:
            self.lockDev = newDev
        elif newDev.id == self.boltDev.id:
            self.boltDev = newDev
        self.updateStatus()

    #-------------------------------------------------------------------------------
    def updateStatus(self):
        devStates = [
            {'key':'onOffState',        'value':self.onState},
            {'key':'door_confirmed',    'value':self.doorBool and self.door_confirmed},
            {'key':'lock_confirmed',    'value':self.lock_confirmed},
            {'key':'bolt_confirmed',    'value':self.boltBool and self.bolt_confirmed},
            {'key':'action_success',    'value':self.action_success},
            {'key':'state',             'value':self.text_state},
            ]
        self.device.updateStatesOnServer(devStates)

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
    if zint(value):
        return  True
    elif isinstance(value, basestring):
        return value.lower() in k_commonTrueStates
    else:
        return False
