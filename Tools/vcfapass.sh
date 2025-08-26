#!/usr/bin/expect -f
set timeout 20
set user [lindex $argv 0]
set host [lindex $argv 1]
set old_password [lindex $argv 2]
set new_password [lindex $argv 3]

spawn ssh $user@$host
expect "(vmware-system-user@10.1.1.71) Password:"
send "$old_password\r"
expect "You are required to change your password immediately (administrator enforced)."
expect "Current password:"
send "$old_password\r"
expect "(vmware-system-user@10.1.1.71) New password:"
send "$new_password\r"
expect "(vmware-system-user@10.1.1.71) Retype new password:"
send "$new_password\r"
expect "vmware-system-user@auto-a-8fpl5 [ ~ ]$"
send "sudo -i\r"
expect "root@auto-a-8fpl5 [ ~ ]#"
send "echo \"$user:$old_password\r\" | chpasswd"
expect eof


