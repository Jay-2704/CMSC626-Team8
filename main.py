import argparse
import os
from datetime import datetime

arg = argparse.ArgumentParser()
arg.add_argument("-s", "--search", type=str, help="Search for a file")
arg.add_argument("-d", "--download", type=str, help="Download a file")
arg.add_argument("-r", "--read", type=str, help="Read a file")
arg.add_argument("-c", "--create", type=str, help="Create a file")
arg.add_argument("-w", "--write", type=str, help="Write to a file (must be used with -m)")
arg.add_argument("-m", "--message", type=str, help="Message to write to a file (to be used with -w)")
arg.add_argument("-x", "--delete", type=str, help="Delete a file from the file system")
arg.add_argument("-z", "--recover", type=str, help="Restore a file previously deleted from the file system")


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
        # If a file with the same name is already deleted, deny the creation in case the owner of the deleted file wants
        # to recover the deleted file later
        deleted = os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " ls /home/cmsc626/Desktop/deleted").read().split('\n')
        if query in deleted:
            return 0
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
            # Remove users from list of people with file who no longer have the latest update
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
        return 2
    else:
        os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " touch /home/cmsc626/Desktop/files/" + location[1] + "/.mutex").read()

    local = os.popen("ls /home/cmsc626/Desktop/files/").read().split('\n')
    if location and location != 2 and location[1] in local:
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
            os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " rm -f /home/cmsc626/Desktop/files/" + location[1] + "/.mutex").read()
            return 1
        else:
            os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " rm -f /home/cmsc626/Desktop/files/" + location[1] + "/.mutex").read()
            return 3
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
                # Copy file from most up-to-date person, copy version from directory, and insert ip to show ownership
                os.popen("sshpass -p 12345 rsync -r cmsc626@" + location[0] + ":/home/cmsc626/Desktop/files/" + location[1] + " files/" + " && "
                         + "sshpass -p 12345 rsync cmsc626@" + directory_server + ":/home/cmsc626/Desktop/files/" + location[1] + "/.version" + " files/" + location[1] + "/.version" + " && "
                         + "sshpass -p 12345 ssh cmsc626@" + directory_server + " touch /home/cmsc626/Desktop/files/" + location[1] + "/" + ip).read()
                return 1
            # If user has the latest version
            else:
                return 2
        # If user does not have the file at all (pretty much do same as above but without version checking)
        else:
            ip = getip()
            # Combine everything because of race conditions
            # Copy file from most up-to-date person, copy version from directory, and insert ip to show ownership
            os.popen("sshpass -p 12345 rsync -r cmsc626@" + location[0] + ":/home/cmsc626/Desktop/files/" + location[1] + " files/" + " && "
                     + "sshpass -p 12345 rsync cmsc626@" + directory_server + ":/home/cmsc626/Desktop/files/" + location[1] + "/.version" + " files/" + location[1] + "/.version" + " && "
                     + "sshpass -p 12345 ssh cmsc626@" + directory_server + " touch /home/cmsc626/Desktop/files/" + location[1] + "/" + ip).read()
            return 1
    else:
        return 0


def delete(query):
    location = search(query)
    if location and location != 2:
        # This is pretty simple. Just move the directory containing the file and the version to a "delete" directory
        # instead of formally deleting it, so it can be recovered later.
        os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " mv /home/cmsc626/Desktop/files/" + location[1] + " /home/cmsc626/Desktop/deleted/" + location[1]).read()
        return 1
    return 0


def recover(query):
    # This is similar to the deletion check in the create file process
    deleted = os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " ls /home/cmsc626/Desktop/deleted").read().split('\n')
    if query not in deleted:
        return 0
    else:
        # Reverse of delete function
        os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " mv /home/cmsc626/Desktop/deleted/" + query + " /home/cmsc626/Desktop/files/" + query).read()
        return 1


if __name__ == "__main__":
    getip()
    if args.search:
        file = search(args.search)
        # Successful search
        if file and file != 2:
            print("File " + str(args.search) + " has been found!")
            os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " \"echo '" + str(datetime.now()) + " --> " +
                     getip() + " successfully searched file " + str(args.search) +
                     "' >> /home/cmsc626/Desktop/log.txt\"")
        # Directory is offline
        elif file == 2:
            print("Directory server not online")
        # File not found
        else:
            print("File " + str(args.search) + " has not been found.")
            os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " \"echo '" + str(datetime.now()) + " --> " +
                     getip() + " unsuccessfully searched file " + str(args.search) + " (not found)" +
                     "' >> /home/cmsc626/Desktop/log.txt\"")

    elif args.read:
        file = read(args.read)
        # Successful read
        if file:
            print(str(args.read) + ": " + file)
            os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " \"echo '" + str(datetime.now()) + " --> " +
                     getip() + " successfully read file " + str(args.read) +
                     "' >> /home/cmsc626/Desktop/log.txt\"")
        # File not found
        else:
            print("File " + str(args.read) + " has not been found")
            os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " \"echo '" + str(datetime.now()) + " --> " +
                     getip() + " unsuccessfully read file " + str(args.read) + " (not found)" +
                     "' >> /home/cmsc626/Desktop/log.txt\"")

    elif args.create:
        file = create(args.create)
        # Successful creation
        if file:
            print("File " + str(args.create) + " has been created!")
            os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " \"echo '" + str(datetime.now()) + " --> " +
                     getip() + " successfully created file " + str(args.create) +
                     "' >> /home/cmsc626/Desktop/log.txt\"")
        # File conflict
        else:
            print("File " + str(args.create) + " could not be created.")
            os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " \"echo '" + str(datetime.now()) + " --> " +
                     getip() + " unsuccessfully created file " + str(args.create) + " (already exists)" +
                     "' >> /home/cmsc626/Desktop/log.txt\"")

    elif args.write:
        file = write_v2(args.write, args.message)
        # Successful write
        if file and file != 2 and file != 3:
            print("Updated file " + str(args.write) + "!")
            os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " \"echo '" + str(datetime.now()) + " --> " +
                     getip() + " successfully wrote file " + str(args.write) +
                     "' >> /home/cmsc626/Desktop/log.txt\"")
        # Mutex lock
        elif file == 2:
            print("Can't modify file " + str(args.write) + " at this time.")
            os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " \"echo '" + str(datetime.now()) + " --> " +
                     getip() + " unsuccessfully wrote file " + str(args.write) + " (mutex lock)" +
                     "' >> /home/cmsc626/Desktop/log.txt\"")
        # Obsolete file
        elif file == 3:
            print("File " + str(args.write) + " has been previously modified. Please pull the updated version.")
            os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " \"echo '" + str(datetime.now()) + " --> " +
                     getip() + " unsuccessfully wrote file " + str(args.write) + " (previously modified)" +
                     "' >> /home/cmsc626/Desktop/log.txt\"")
        # File not found
        else:
            print("File " + str(args.write) + " has not been found.")
            os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " \"echo '" + str(datetime.now()) + " --> " +
                     getip() + " unsuccessfully wrote file " + str(args.write) + " (not found)" +
                     "' >> /home/cmsc626/Desktop/log.txt\"")


    elif args.download:
        file = download(args.download)
        # Successful download
        if file and file != 2:
            print("File " + str(args.download) + " has been successfully downloaded!")
            os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " \"echo '" + str(datetime.now()) + " --> " +
                     getip() + " successfully downloaded file " + str(args.download) +
                     "' >> /home/cmsc626/Desktop/log.txt\"")
        # Up-to-date file
        elif file == 2:
            print("You already have the latest version of file " + str(args.download) + ".")
            os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " \"echo '" + str(datetime.now()) + " --> " +
                     getip() + " unsuccessfully downloaded file " + str(args.download) + " (up-to-date)" +
                     "' >> /home/cmsc626/Desktop/log.txt\"")
        # File not found
        else:
            print("File " + str(args.download) + " has not been found.")
            os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " \"echo '" + str(datetime.now()) + " --> " +
                     getip() + " unsuccessfully downloaded file " + str(args.download) + " (not found)" +
                     "' >> /home/cmsc626/Desktop/log.txt\"")

    elif args.delete:
        file = delete(args.delete)
        # Successful deletion
        if file:
            print("Successfully deleted file " + str(args.delete) + ".")
            os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " \"echo '" + str(datetime.now()) + " --> " +
                     getip() + " successfully deleted file " + str(args.delete) +
                     "' >> /home/cmsc626/Desktop/log.txt\"")
        # File not found
        else:
            print("Unable to delete file " + str(args.delete) + ".")
            os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " \"echo '" + str(datetime.now()) + " --> " +
                     getip() + " unsuccessfully deleted file " + str(args.delete) + " (not found)" +
                     "' >> /home/cmsc626/Desktop/log.txt\"")

    elif args.recover:
        file = recover(args.recover)
        # Successful recovery
        if file:
            print("Successfully restored file " + str(args.recover) + ".")
            os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " \"echo '" + str(datetime.now()) + " --> " +
                     getip() + " successfully recovered file " + str(args.recover) +
                     "' >> /home/cmsc626/Desktop/log.txt\"")
        # File not found
        else:
            print("File " + str(args.recover) + " has not been found.")
            os.popen("sshpass -p 12345 ssh cmsc626@" + directory_server + " \"echo '" + str(datetime.now()) + " --> " +
                     getip() + " unsuccessfully recovered file " + str(args.recover) + " (not found)" +
                     "' >> /home/cmsc626/Desktop/log.txt\"")

    # Invalid user input
    else:
        print("Please enter a valid flag. Use --help to see all options.")
