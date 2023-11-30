import argparse
import os
import socket

arg = argparse.ArgumentParser()
arg.add_argument("-s", "--search", type=str, help="Search for a file")
arg.add_argument("-d", "--download", type=str, help="Download a file")
arg.add_argument("-r", "--read", type=str, help="Read a file")
arg.add_argument("-c", "--create", type=str, help="Create a file")
arg.add_argument("-w", "--write", type=str, help="Write to a file (must be used with -m)")
arg.add_argument("-m", "--message", type=str, help="Message to write to a file (to be used with -w)")

args = arg.parse_args()

directory_server = "192.168.1.4"


def getip():
    ip = os.popen("ip a").read().split('\n')
    for i in ip:
        i = i.strip()
        if "inet" in i:
            if "127.0.0.1" in i or "::" in i:
                continue
            else:
                return i.split(" ")[1].split("/")[0]
    return 0


def search(query):
    ping = os.popen("ping -c 1 -w 1 " + str(directory_server)).read()
    if "100% packet loss" in ping:
        return 2
    files = os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " ls /home/cmsc626/Desktop/files").read().split('\n')
    for file in files:
        if file.lower() == str(query).lower():
            users = os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " ls /home/cmsc626/Desktop/files/" + file).read().split('\n')
            for user in users:
                if user != '':
                    ping = os.popen("ping -c 1 -w 1 " + str(user)).read()
                    if "100% packet loss" not in ping:
                        return [user, file]
    return 0


def read(query):
    location = search(query)
    if location and location != 2:

        # If the current user is the one who owns the most recent file
        if location[0] == getip():
            return os.popen("cat files/"+location[1]+"/"+location[1]).read()
        else:
            return os.popen("sshpass -p 12345 ssh cmsc626@" + location[0] + " cat /home/cmsc626/Desktop/files/" + location[1] + "/" + location[1]).read()
    else:
        return 0


def create(query):
    # Fail if file already exists
    if search(query) and search(query) != 2:
        return 0
    else:
        ip = getip()
        # Combine everything cause race conditions
        # Establish new file's presence on directory server and make file locally
        os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " mkdir /home/cmsc626/Desktop/files/" + query +
                 " && sshpass -p 12345 ssh cmsc626@" + directory_server + " touch /home/cmsc626/Desktop/files/" + query + "/" + ip +
                 " && mkdir " + "files/" + query + " && " + "touch " + "files/" + query + "/" + query + " && " + "touch " + "files/" + query + "/" + ".version" +
                 " && echo \'1\n" + ip + "\' > " + "files/" + query + "/" + ".version" +
                 " && sshpass -p 12345 rsync files/" + query + "/" + ".version" + " cmsc626@" + directory_server + ":/home/cmsc626/Desktop/files/" + query + "/.version").read()
        return 1


# THIS IS DEPRECATED BUT WE HAVE DECIDED TO KEEP THIS HERE FOR LEGACY PURPOSES AND TO SEE OUR THOUGHT PROCESS
# Make changes locally, check version, push changes. Revert if wrong
def write(query, text):
    location = search(query)
    if location and location != 2:
        # Get initial version
        version = open("files/" + location[1] + "/" + ".version").read().split()
        print(version[0])
        ip = getip()

        # Modify the file to reflect changes
        newfile = open("files/" + location[1] + "/" + location[1], "w")
        newfile.write(text)
        newfile.close()

        # Modify version to reflect changes
        updated = open("files/" + location[1] + "/" + ".version", "w")
        updated.write(str(int(version[0])+1) + "\n" + ip)
        updated.close()

        # Get new version number
        version = open("files/" + location[1] + "/" + ".version").read().split()
        print(version)
        remote_version = os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " cat /home/cmsc626/Desktop/files/" + location[1] + "/" + ".version").read().split("\n")

        print(remote_version)

        # Compare version locally to what is on the remote server
        # If the version is now greater than what is on remote server, proceed with change
        if int(version[0]) > int(remote_version[0]):
            os.popen("sshpass -p 12345 rsync files/" + location[1] + "/" + ".version" + " cmsc626@" + directory_server + ":/home/cmsc626/Desktop/files/" + location[1] + "/.version")
            users = os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " ls /home/cmsc626/Desktop/files/" + location[1]).read().split('\n')
            remote_version = os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " cat /home/cmsc626/Desktop/files/" + location[1] + "/" + ".version").read().split("\n")
            # Exclude the user from the purge who just pushed the file
            exclude = remote_version[1]
            # Remove users from list of people with file who no longer have latest update
            for user in users:
                if user != exclude and user != ".version" and user != location[1]:
                    os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " rm -f /home/cmsc626/Desktop/files/" + location[1] + "/" + user).read()
            print("Updated file " + query + "!")
            return 1
        # Revert changes if file version is less than what is on the directory server
        else:
            print("File has been modified. Please pull the updated version")
            downgraded = open("files/" + location[1] + "/" + ".version", "w")
            downgraded.write(remote_version[0] + "\n" + remote_version[1])
            downgraded.close()
            return 0
    print("File does not exist")
    return 0


# Check version, make changes locally, then push changes. No revert needed if wrong
def write_v2(query, text):
    location = search(query)

    # Works with a mutex file to deal with concurrent writes
    files = os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " ls /home/cmsc626/Desktop/files/" + location[1]).read().split('\n')
    if ".mutex" in files:
        print("Can't modify file at this time")
        return 0
    else:
        os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " touch /home/cmsc626/Desktop/files/" + location[1] + "/.mutex").read()

    if location and location != 2:
        # Get initial versions
        version = open("files/" + location[1] + "/" + ".version").read().split()
        remote_version = os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " cat /home/cmsc626/Desktop/files/" + location[1] + "/" + ".version").read().split("\n")

        # If the next version number is higher than what is recorded on the directory server
        if int(version[0])+1 > int(remote_version[0]):
            ip = getip()

            # Update the version file
            updated = open("files/" + location[1] + "/" + ".version", "w")
            updated.write(str(int(version[0]) + 1) + "\n" + ip)
            updated.close()

            # Update the actual text file
            newfile = open("files/" + location[1] + "/" + location[1], "w")
            newfile.write(text)
            newfile.close()

            # Copy the new version file to the directory server
            os.popen("sshpass -p 12345 rsync files/" + location[1] + "/" + ".version" + " cmsc626@" + directory_server + ":/home/cmsc626/Desktop/files/" + location[1] + "/.version")
            # Exclude the user from the purge who just pushed the file
            exclude = ip
            users = os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " ls /home/cmsc626/Desktop/files/" + location[1]).read().split('\n')
            # Purge all users who own the file because their versions are now outdated
            for user in users:
                if user != exclude and user != ".version" and user != location[1]:
                    os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " rm -f /home/cmsc626/Desktop/files/" + location[1] + "/" + user).read()
            print("Updated file " + query + "!")
            os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " rm -f /home/cmsc626/Desktop/files/" + location[1] + "/.mutex").read()
            return 1
        else:
            print("File has been previously modified. Please pull the updated version.")
            os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " rm -f /home/cmsc626/Desktop/files/" + location[1] + "/.mutex").read()
            return 0
    print("File does not exist")
    os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " rm -f /home/cmsc626/Desktop/files/" + location[1] + "/.mutex").read()
    return 0


def download(query):
    location = search(query)
    if location and location != 2:
        # Check if user currently owns file
        if os.path.exists("files/" + location[1] + "/" + ".version"):
            remote_version = os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " cat /home/cmsc626/Desktop/files/" + location[1] + "/" + ".version").read().split("\n")
            version = open("files/" + location[1] + "/" + ".version").read().split()
            ip = getip()
            # Check to see if user's version is obsolete
            if version[0] < remote_version[0] and ip != remote_version[1]:
                ip = getip()
                # Combine everything because of race conditions
                # Copy file from most up to date person, copy version from directory, and insert ip to show ownership
                os.popen("sshpass -p 12345 rsync -r cmsc626@" + location[0] + ":/home/cmsc626/Desktop/files/" + location[1] + " files/" + " && "
                         + "sshpass -p 12345 rsync cmsc626@" + directory_server + ":/home/cmsc626/Desktop/files/" + location[1] + "/.version" + " files/" + location[1] + "/.version" + " && "
                         + "sshpass -p 12345 ssh cmsc626@" + directory_server + " touch /home/cmsc626/Desktop/files/" + location[1] + "/" + ip).read()
                print("File " + query + " has been successfully downloaded!")
                return 1
            # If user has latest version
            else:
                print("You already have the latest version")
                return 0
        # If user does not have the file at all (pretty much do same as above but without version checking)
        else:
            ip = getip()
            # Combine everything because of race conditions
            # Copy file from most up to date person, copy version from directory, and insert ip to show ownership
            os.popen("sshpass -p 12345 rsync -r cmsc626@" + location[0] + ":/home/cmsc626/Desktop/files/" + location[1] + " files/" + " && "
                     + "sshpass -p 12345 rsync cmsc626@" + directory_server + ":/home/cmsc626/Desktop/files/" + location[1] + "/.version" + " files/" + location[1] + "/.version" + " && "
                     + "sshpass -p 12345 ssh cmsc626@" + directory_server + " touch /home/cmsc626/Desktop/files/" + location[1] + "/" + ip).read()
            print("File " + query + " has been successfully downloaded!")
            return 1
    else:
        print("File not found")
        return 0


if __name__ == "__main__":
    getip()
    if args.search:
        file = search(args.search)
        if file:
            if file == 2:
                print("Directory server not online")
            else:
                print("File " + str(args.search) + " has been found!")
        else:
            print("File " + str(args.search) + " has not been found.")

    elif args.read:
        file = read(args.read)
        if file:
            print(str(args.read) + ": " + file)
        else:
            print("File " + str(args.read) + " not found")

    elif args.create:
        file = create(args.create)
        if file:
            print("File " + str(args.create) + " has been created!")
        else:
            print("File " + str(args.create) + " could not be created.")

    elif args.write:
        write_v2(args.write, args.message)

    elif args.download:
        download(args.download)

    else:
        print("Please enter a valid flag. Use --help to see all options.")
