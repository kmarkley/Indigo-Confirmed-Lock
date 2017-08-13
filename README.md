# Confirmed Lock
This plugin combines lock devices with (optional) door and deadbolt sensors to provide additional confirmation that a lock is actually, literally, really truly locked.

Lock and unlock commands sent to the plugin device will cause the plugin to attempt multiple times to lock or unlock the physical lock device, until confirmation is obtained.

If the plugin fails to confirm the state of the physical lock, the plugin will optionally execute Action Group may be executed, as well as optionally create a Pester to repeat the Action Group.

## Confirmed Lock devices

#### Configuration

* **Select Lock Device**  
Select the lock you wish to confirm.
* **Number of attempts**  
Number of times to attempt to lock/unlock the physical lock device
* **Delay between attempts**  
Self explanatory.
* **Door sensor?**  
Check if there exists an independent sensor for the door open/close state.
    * **Door sensor device**  
    Select the door sensor device.
    * **State**  
    Select the device state for the door sensor
    * **Value when closed**  
    What is the state value when the door is closed?
* **Deadbolt sensor?**  
Check if there exists an independent sensor for the deadbolt.
    * **Deadbolt sensor device**  
    Select the deadbolt sensor device.
    * **State**  
    Select the device state for the daedbolt sensor
    * **Value when engaged**  
    What is the state value when the deadbolt is fully engaged?
    * **Deadbolt sensor delay**  
    How long to wait for the lock mechanism before checking the deadbolt sensor.
* **Message to variable**  
Check to write set a variable on failure.
    * **Variable**  
    Select the variable.
    * **Message**  
    Enter the new value for the variable.  Standard text substitutions apply.  
    The variable will be set to the empty string on any successful lock confirmation.
* **Failure action?**  
Check to execute an Action Group if the plugin fails to confirm the lock state.
    * **Select action group**  
    Select the Action Group to execute on failure.
    * **Pester Cycles**  
    Enter a number to create a Pester that repeats the Action Group execution.  
    Set to zero or blank to not create a Pester.  
    Pesters will be canceled on any successful lock confirmation.
    * **Pester time (sec)**  
    Enter the number of seconds between Pester cycles.
    * **Final action Group**  
    Optionally select a different Action Group to be executed on the last Pester cycle.

#### States

* **bolt_confirmed** (bool): true if the deadbolt sensor reports deadbolt fully engaged.
* **door_confirmed** (bool): true if the door sensor reports the door is closed.
* **locked_confirmed** (bool): true if the lock device reports being locked.
* **pester_active** (bool): true if a pester was created since the last successful confirmation.
* **state** (enum): one of
    * **open**: the door is open
    * **unlocked**: the lock is unlocked
    * **unconfirmed** the lock reports being locked, but the deadbolt sensor does not confirm.
    * **confirmed**: confirmed fully locked

## Dummy Lock devices

Handy for testing, these devices look like locks in Indigo, but don't do anything beyond report a locked or unlocked state.

## Actions

Plugin devices respond to standard Indigo **lock** and **unlock** commands.  
No custom actions defined.
