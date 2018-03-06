# Confirmed Lock
This plugin combines lock devices with (optional) door and deadbolt sensors to provide additional confirmation that a lock is actually, literally, really, truly locked.

Lock and unlock commands sent to the plugin device will cause the plugin to attempt multiple times to lock or unlock the physical lock device, until confirmation is obtained.

If the plugin fails to confirm the state of the physical lock, the plugin will optionally execute an Action Group, as well as optionally create a Pester to repeat the Action Group.
