import fileinput
import socket
import hashlib
import os
from time import sleep
import subprocess
import re

UDP_PORT_OUT = 1375
UDP_PORT_IN = 1376
RecvSocket = 0
RetryCountMD5 = 15
FileSizeInt = 0
SettingsFilePath = "/boot/openhd-settings-1.txt"
SwitchToFreq = "0"
DefaultCommunicateFreq = "2412"

SettingsFilePath = "/boot/openhd-settings-1.txt"
TxPowerConfigFilePath="/etc/modprobe.d/ath9k_hw.conf"
TxPowerFromConfig="-1"
TxPowerFromAth9k_hw="-1"


WlanName = "0"
SettingsFileDATARATE = "0"
SettingsFileTXPOWER = "0"
SettingsFileTXMODE = "0"
#SmartSync_StartupMode = "-1"


def SendData(MessageBuf):
    try:
        sockToAir = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
        sockToAir.sendto( bytes(MessageBuf,'utf-8'), ('127.0.0.1', UDP_PORT_OUT))
    except Exception as e:
        print(e)
        return False

def InitUDPServer():
    global RecvSocket
    UDP_IP = ""
    try:
        RecvSocket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        RecvSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        RecvSocket.settimeout(0.3)
        RecvSocket.bind((UDP_IP, UDP_PORT_IN))
    except Exception as e:
        print(e)
        return False

def RecvPacket():
    try:
            data, addr = RecvSocket.recvfrom(1200)
            return data
    except Exception as e:
        print(e)
        return False



def RequestSettingsFile():
    #recv packet header: 6 bytes offset + data up to 1024. Max 1030 bytes
    InBuffer = ""
    offset = 0
    isReceived = False
    MessageBufFile =  bytearray()

    while isReceived == False:
        try:
            if offset < FileSizeInt:
                SendBuff = "RequestSFile"
                SendBuff +=  '{:0>6}'.format(offset)
                SendData(SendBuff)
                tmp = RecvPacket()
                if tmp != False:
                    InMsgLen = len(tmp)
                    RecvPacketOffset = int(tmp[0:6])
                    if RecvPacketOffset == offset:
                        MessageBufFile.extend(tmp[6:InMsgLen])
                        offset += InMsgLen-6
                        print("File block received, offset", offset)
                    else:
                        print("Wrong packet, ignore")
                else:
                    print("Recv file block error. Retry...")
                sleep(0.05)
            else:
                isReceived = True
        except Exception as e:
            print(e)
    return MessageBufFile

def SaveFile(Buf, path):
    try:
        hfile = open(path, "wb")
        hfile.write(Buf)
        hfile.close()
        return True
    except Exception as e:
            print(e)
            return False
    return True

def md5(fname):
    try:
        hash_md5 = hashlib.md5()
        with open(fname, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest().encode('ascii')
    except Exception as e:
       print(e)
       return False

def RequestMd5FileSize():
    global FileSizeInt
    FailCounter = 0

    for FailCounter in range(0, RetryCountMD5):
        SendData("RequestGroundChecksum")
        result = RecvPacket()
        if result != False:
            StrLen = len(result)
            if StrLen > 33: #32 bytes md5, after 32byte - file size
                #Get MD5CheckSum
                MD5CheckSum = result[0:32]
                print("Ground settings file MD5: ", MD5CheckSum)
                #Get FileSize
                FileSizeStr = result[32:StrLen]
                FileSizeInt = int(FileSizeStr)
                print("Settings file size in bytes: ", FileSizeInt)
                return MD5CheckSum

        else:
            FailCounter+= 1
            print("RequestMd5FileSize error. Retry: ", FailCounter )
    return False

def NotifyGroundWithACK(message):
    SendData(message)
    result = RecvPacket()
    if result != False:
        tmp = "ACK".encode('ascii')
        if result == tmp:
            return True
        else:
            return False
    return False

def MoveFile():
    os.system('mount -o remount,rw /boot')
    os.system('cp /tmp/infile.txt /boot/openhd-settings-1.txt')
    os.system('sync')
    os.system('mount -o remount,ro /boot')
    print("copy file process completed.")

def GetFreqFromConfig():
    try:
        with open(OpenHDSettingsFile, "r") as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith("FREQ=") == True:
                    SplitLines = line.split("=")
                    FilterDigits = SplitLines[1]
                    result = re.sub("\D", "", FilterDigits)
                    return result

    except Exception as e:
       print(e)
       return False
    return False




def StartSVPcomTx():                                     
    try: 
        subprocess.Popen(['/home/pi/cameracontrol/IPCamera/svpcom_wifibroadcast/wfb_tx', "-k", "1", "-n", "1", "-K", "/home/pi/cameracontrol/IPCamera/svpcom_wifibroadcast/tx.key",  "-u" ,str(UDP_PORT_OUT), "-p", "92", "-B", "20", "-M", "0", WlanName ] )
        return True
    except Exception as e:
        print(e)
        return False
    return False

def StartSVPcomRx():   
    try:       
        
        subprocess.Popen( ['/home/pi/cameracontrol/IPCamera/svpcom_wifibroadcast/wfb_rx', "-k", "1", "-n", "1", "-K", "/home/pi/cameracontrol/IPCamera/svpcom_wifibroadcast/rx.key",  "-c" ,"127.0.0.1", "-u", str(UDP_PORT_IN), "-p", "93",  WlanName ] )
        return True
    except Exception as e:
        print(e)
        return False
    return False

def StartConfigureWlanScript():   
    try:       
        subprocess.check_call(['/home/pi/RemoteSettings/Air/helper/ConfigureNicsAir.sh', SettingsFileDATARATE, DefaultCommunicateFreq, "single" ])
        return True
    except Exception as e:
        print(e)
        return False
    return False


def FindWlanToUseAir():
    global WlanName

    print("Trying to init WLAN...")
    try:
        for root, dirs, files in os.walk("/sys/class/net/"):
            for dir in dirs:
                if dir.startswith("eth") == False and  dir.startswith("lo") == False and  dir.startswith("usb") == False and  dir.startswith("intwifi") == False and  dir.startswith("relay") == False and dir.startswith("wifihotspot") == False:
                    print("Found WLan with name: ", dir)
                    WlanName = dir
        if WlanName != "0":
            print("Using WLAN with name: ", WlanName)
            subprocess.check_call(['/sbin/iw', "dev", WlanName , "set", "freq", DefaultCommunicateFreq ])
            return True
        else:
            return False

    except Exception as e:
        print(e)
        return False
 
def ReturnWlanFreq():
    if WlanName != "0":
        try:
            SettingsFileFREQ = "0"
            with open(SettingsFilePath, "r") as f:
                lines = f.readlines()
                for line in lines:
                    if line.startswith("FREQ=") == True:
                        SplitLines = line.split("=")
                        FilterDigits = SplitLines[1]
                        SettingsFileFREQ = re.sub("\D", "", FilterDigits)
                        
            if SettingsFileFREQ == "0":
                #subprocess.check_call(['/sbin/iw', "dev", WlanName , "set", "freq", "2472" ])
                subprocess.check_call(['/home/pi/RemoteSettings/Air/SetWlanFreq.sh', WlanName , "2472" ])
                print("Can`t read frequency from config file. Frequency set to: 2472")
            else:
                #subprocess.check_call(['/sbin/iw', "dev", WlanName , "set", "freq", SettingsFileFREQ ])
                subprocess.check_call(['/home/pi/RemoteSettings/Air/SetWlanFreq.sh', WlanName , SettingsFileFREQ ])
                print("Frequency for WLAN: " + WlanName + " returned back to: " + SettingsFileFREQ)

            
        except Exception as e:
            print(e)

def ReadSettingsFromConfigFile():
    global SettingsFileDATARATE
    global SettingsFileFREQ
    global SettingsFileTXPOWER
    global SettingsFileTXMODE
#   global SmartSync_StartupMode

    try:
        with open(SettingsFilePath, "r") as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith("DATARATE") == True:
                    SplitLines = line.split("=")
                    FilterDigits = SplitLines[1]
                    SettingsFileDATARATE = re.sub("\D", "", FilterDigits)

#                if line.startswith("SmartSync_StartupMode") == True:
#                    SplitLines = line.split("=")
#                    FilterDigits = SplitLines[1]
#                    SmartSync_StartupMode = int(re.sub("\D", "", FilterDigits) )

                if line.startswith("TXPOWER") == True:
                    SplitLines = line.split("=")
                    FilterDigits = SplitLines[1]
                    SettingsFileTXPOWER = re.sub("\D", "", FilterDigits)

                if line.startswith("TXMODE") == True:
                    SplitLines = line.split("=")
                    FilterDigits = SplitLines[1]
                    SettingsFileTXMODE = re.sub("\D", "", FilterDigits)

            return True


    except Exception as e:
       print(e)
       return False
    return False


def InitSettings():
    global SettingsFileDATARATE
    global SettingsFileTXPOWER
    global SettingsFileTXMODE

    ReadSettingsFromConfigFile()
    
    if SettingsFileDATARATE == "0":
        print("Can't read DATARATE. Set DATARATE=4")
        SettingsFileDATARATE = "4"


    if SettingsFileTXPOWER == "0":
        SettingsFileTXPOWER = "2000"

    if SettingsFileTXMODE == "0":
        SettingsFileTXMODE = "single"

def ReadTxPowerAth9k_hw():
    global TxPowerFromAth9k_hw
    try:
        with open(TxPowerConfigFilePath, "r") as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith("options ath9k_hw txpower") == True:
                    SplitLines = line.split("=")
                    FilterDigits = SplitLines[1]
                    TxPowerFromAth9k_hw = re.sub("\D", "", FilterDigits)

            return True

    except Exception as e:
       print(e)
       return False
    return False


def ReadTxPower():
    global TxPowerFromConfig
    try:
        with open(SettingsFilePath, "r") as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith("TxPowerAir") == True:
                    SplitLines = line.split("=")
                    FilterDigits = SplitLines[1]
                    TxPowerFromConfig = re.sub("\D", "", FilterDigits)

            return True

    except Exception as e:
       print(e)
       return False
    return False


def CheckTxPower():
    try:
        if ReadTxPowerAth9k_hw() != False:
            print("TxPowerFromAth9k_hw= " + TxPowerFromAth9k_hw)
            if ReadTxPower() != False:
                print("TxPowerFromConfig= " + TxPowerFromConfig)
                if TxPowerFromConfig != TxPowerFromAth9k_hw:
                    print("TxPower not equal Check if all ok and apply")
                    if TxPowerFromAth9k_hw != "-1" and TxPowerFromConfig != "-1":
                        print("all ok, apply")
                        subprocess.check_call(['/usr/local/bin/txpower_atheros', TxPowerFromConfig ] )
                        return True
    except Exception as e:
        print(e)
        return False
    return False


def CleanAndExit():
    CheckTxPower()
    print("SmartSync done.")
    ReturnWlanFreq()
    sleep(1)
    RecvSocket.close()

    try:
        subprocess.check_call(['/usr/bin/killall', "JoystickSender" ]) 
    except Exception as e:
        print(e)

    try:
        subprocess.check_call(['/usr/bin/killall', "wfb_rx" ]) 
    except Exception as e:
        print(e)

    try:
        subprocess.check_call(['/usr/bin/killall', "wfb_tx" ]) 
    except Exception as e:
        print(e)


    exit()

#########################################################Start

if os.path.isfile("/tmp/ReadyToGo") == True:
    print("No need to run second time")
    exit()

InitSettings()



if StartConfigureWlanScript() != False:
    if FindWlanToUseAir() != False:
        if StartSVPcomRx() != False:
            print("StartSVPcomRx")
            if StartSVPcomTx() != False:
                print("StartSVPcomTx")
                InitUDPServer()
                MD5CheckSumGround = RequestMd5FileSize()
                if MD5CheckSumGround != False:
                    MD5CheckSumAirCurrent = md5(SettingsFilePath)
                    if MD5CheckSumGround == MD5CheckSumAirCurrent:
                        print("Air and Ground config files equal. No need in sync")
                        print("Notify ground that it can boot.")
                        IsACK_RetryCounter = 0
                        for i in range(0,15):
                            IsACK = NotifyGroundWithACK("NoNeedInSync")
                            if IsACK == True:
                                CleanAndExit()
                            sleep(0.1)
                        CleanAndExit()
                    else:
                        print("Air and Ground config mismatch. Sync required")
                        while True:
                            InFileBuff = RequestSettingsFile()
                            SaveFile(InFileBuff,"/tmp/infile.txt")
                            InFileHash = md5("/tmp/infile.txt")
                            print("InFileMD5: ", InFileHash)
                            if InFileHash == MD5CheckSumGround:
                                print("Ground and downloaded file checksum equal.")
                                print("ACK received. Moving tmp file to /boot...")
                                MoveFile()
                                for x in range(0,15):
                                    IsACK = NotifyGroundWithACK("DownloadFinished")
                                    if IsACK == True:
                                        print("ACK received. ready to boot")
                                        CleanAndExit()
                                        break
                                CleanAndExit()

                                #while True:
                                #    IsACK = NotifyGroundWithACK("DownloadFinished")
                                #    if IsACK == True:
                                #        print("ACK received. Moving tmp file to /boot...")
                                #        MoveFile()
                                #        CleanAndExit()
                                #    print("NotifyGroundWithACK failed. Retry...")
                                #    IsACK_RetryCounter += 1
                                #    if IsACK_RetryCounter % 2 == 0:
                                #        if SwitchToFreq == "0":
                                #            print("Reading freq from file...")
                                #            SwitchToFreq = GetFreqFromConfig()
                                #            if SwitchToFreq == False:
                                #                print("Failed to read freq from settings file")
                                #                SwitchToFreq = "0"
                                #            else:
                                #                print("Ground main frequency is: ", SwitchToFreq)
                                #                print("switching to frequency: ", SwitchToFreq )
                                #                SwitchWlanToFreq(SwitchToFreq)
                                #
                                #        else:
                                #            print("switching to frequency: ", SwitchToFreq)
                                #            SwitchWlanToFreq(SwitchToFreq)
                                #
                                #    else:
                                #        print("switching to default frequency: ", DefaultCommunicateFreq)
                                #        SwitchWlanToFreq(DefaultCommunicateFreq)

                                #    sleep(1) #wait a bit between ACK request resend. 

                                #break
                            else:
                                print("Downloaded file checksum not match to Ground. Retry...")


                else:
                    print("Failed to request ground MD5 config checksum. Current config file will be loaded.")
else:
    print("Faile to start /home/pi/RemoteSettings/Air/helper/ConfigureNicsAir.sh file")

CleanAndExit()
