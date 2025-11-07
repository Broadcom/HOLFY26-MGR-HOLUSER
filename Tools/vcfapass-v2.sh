#!/usr/bin/expect -f
# HOL Usage: vcfapass.sh $(cat ~/creds.txt) $(cat ~/NEWPASSWORD.txt)
#     Note: NEWPASSWORD.txt is created in the labstartup.sh by calling the holpwgen.sh script
set timeout 20
set old_password [lindex $argv 0]
set new_password [lindex $argv 1]

spawn ssh vmware-system-user@10.1.1.71

# Expect the initial password prompt
expect "(vmware-system-user@10.1.1.71) Password:" {
  send "$old_password\r"
}

# Now watch for the outcomes:

# OUTCOME 1: Password Expired (Prompted to change it)
expect {
    "You are required to change your password immediately (administrator enforced)." {
    expect "Current password:"
    send "$old_password\r"
    expect "(vmware-system-user@10.1.1.71) New password:"
    send "$new_password\r"
    expect "(vmware-system-user@10.1.1.71) Retype new password:"
    send "$new_password\r"
    expect "vmware-system-user@auto-a-8fpl5 "
    send "sudo -i\r"
    expect "root@auto-a-8fpl5 "
    send "passwd vmware-system-user\r"
    expect "New password:"
    send "$old_password\r"
    expect "Retype new password:"
    send "$old_password\r"
    expect "vmware-system-user@auto-a-8fpl5 " { exit 0}
  }

  # OUTCOME 2: Succesful login (no password change needed)
  "vmware-system-user@auto-a-8fpl5 " {
    send "exit\r"
    expect eof
    exit 0
  }

  # Add a timeout/failure case if needed
  timeout {
    puts "Timeout occurred or unexpected prompt"
    exit 1  
  }
}
