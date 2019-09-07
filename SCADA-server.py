#!/usr/bin/env python

#---------------------------------------------------------------------------# 
# import the modbus libraries we need
#---------------------------------------------------------------------------# 
from pymodbus.server.asynchronous import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.transaction import ModbusRtuFramer, ModbusAsciiFramer

#---------------------------------------------------------------------------# 
# import the twisted libraries we need
#---------------------------------------------------------------------------# 
from twisted.internet.task import LoopingCall

#---------------------------------------------------------------------------# 
# import wiringPi
#---------------------------------------------------------------------------# 
import wiringpi

#---------------------------------------------------------------------------# 
# DHT sensor configuration
#---------------------------------------------------------------------------#
import sys
import Adafruit_DHT

sensor = Adafruit_DHT.DHT11
pin = 14

#---------------------------------------------------------------------------# 
# Threading
#---------------------------------------------------------------------------#
from threading import Thread
from time import sleep
threadDelay = 3


#---------------------------------------------------------------------------#
# Google Document - gspread
#---------------------------------------------------------------------------# 
import sys
import time
import datetime
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

# Account details for google docs
spreadsheet = 'scadasheet'
#json_key = json.load(open('JSON FILE'))                                    <<< ============== enter your json file
scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']

#---------------------------------------------------------------------------# 
# DHT11 callback process
#---------------------------------------------------------------------------# 
def updating_writer_DHT11():

    #Google Docs configuration
    credentials = ServiceAccountCredentials.from_json_keyfile_name('JSON FILE', scope)  #<<< ============== enter your json file
 
    # Login with your Google account
    try:
      gc = gspread.authorize(credentials)
    except:
      print "Unable to log in.  Check your email address/password"
      sys.exit()

    # Open a worksheet from your spreadsheet using the filename
    try:
      worksheet = gc.open(spreadsheet).sheet1

    except:
      print "Unable to open the spreadsheet.  Check your filename: %s" % spreadsheet
      sys.exit()

    last_row = worksheet.row_count
    all_rows = worksheet.col_values(1)
    index = 1
    for cell in all_rows:
      if cell is None:
        break
      else:
        index += 1

 
    global humidity, temperature
    while 1:

	humidity, temperature = Adafruit_DHT.read_retry(sensor, pin)
	    
	
	if humidity is None or temperature is None:
	    humidity, temperature = Adafruit_DHT.read_retry(sensor, pin)
	
	if humidity is None or temperature is None:
	    humidity, temperature = (0, 0)

	string = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
	print string + ': Temp={0:0.1f}*  Humidity={1:0.1f}%'.format(temperature, humidity)

        # Append the data in the spreadsheet, including a timestamp
        try:
            values = [datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), temperature, humidity]
            if index >= last_row:
                print "worksheet resize"
                worksheet.resize(last_row*2, worksheet.col_count)
                last_row = worksheet.row_count
            worksheet.insert_row(values, index)
            index += 1
        except:
            print "Unable to append data.  Check your connection?"


            # Login with your Google account
            try:
                print "Reconnection: authorization"
                gc = gspread.authorize(credentials)
            except:
                print "Reconnection: Unable to log in.  Check your email address/password"
                sys.exit()

            # Open a worksheet from your spreadsheet using the filename
            try:
                print "Reconnection: opening"
                worksheet = gc.open(spreadsheet).sheet1

            except:
                print "Reconnection: Unable to open the spreadsheet.  Check your filename: %s" % spreadsheet
                sys.exit()
                
            try:
                print "Reconnection: insert"
                worksheet.insert_row(values, index)
                index += 1
            except:
                print "Reconnection: Total error"
                sys.exit()
        
	#delay
	sleep(threadDelay)

#---------------------------------------------------------------------------# 
# Heartbit callback process
#---------------------------------------------------------------------------# 
def updating_writer_Heartbit():
  
    global heartbit
    while 1:

	heartbit += 1
	#delay 1 seconds
	sleep(1)

#---------------------------------------------------------------------------# 
# GPIO callback process
#---------------------------------------------------------------------------# 
io = wiringpi.GPIO(wiringpi.GPIO.WPI_MODE_PINS)
io.pinMode(1, io.INPUT)
io.pinMode(2, io.INPUT)
io.pinMode(3, io.OUTPUT)
io.pinMode(4, io.OUTPUT)

def updating_writer_GPIO():

    global register_GPIO_INPUT, register_GPIO_OUTPUT

    while 1:
        #GPIO Reading
        
        #GPIO 1 - reading - SWITCH 1
        if io.digitalRead(1) == io.HIGH:
            register_GPIO_INPUT |= 0x01
        else:
            register_GPIO_INPUT &= 0xFE

        #GPIO 2 - reading - SWITCH 2
        if io.digitalRead(2) == io.HIGH:
            register_GPIO_INPUT |= 0x02
        else:
            register_GPIO_INPUT &= 0xFD

        #GPIO Writing
         
        #GPIO 3 - writing - LED
        if register_GPIO_OUTPUT & 0x01:
            io.digitalWrite(3, io.HIGH)
        else:
            io.digitalWrite(3, io.LOW)

        #GPIO 4 - writing - RELAY (control by GND)
        if register_GPIO_OUTPUT & 0x02:
            io.digitalWrite(4, io.LOW)
        else:
            io.digitalWrite(4, io.HIGH)

        sleep(0.5)

#---------------------------------------------------------------------------# 
# callback process
#---------------------------------------------------------------------------# 
def updating_writer(a):


    global humidity, temperature, heartbit
    global register_GPIO_INPUT, register_GPIO_OUTPUT
	
    #log.debug("updating the context")
    context  = a[0]
    register = 3
    slave_id = 0x00
    address  = 0x00
    values   = context[slave_id].getValues(register, address, count=5)
    
    values[0] = heartbit
    values[1] = temperature
    values[2] = humidity
   
    #GPIO - reading
    values[3] = register_GPIO_INPUT

    #GPIO - writing
    register_GPIO_OUTPUT = values[4]

    #log.debug("new values: " + str(values))
    context[slave_id].setValues(register, address, values)

#---------------------------------------------------------------------------# 
# initialize your data store
#---------------------------------------------------------------------------# 
store = ModbusSlaveContext(
    di = ModbusSequentialDataBlock(0, [1]*100),
    co = ModbusSequentialDataBlock(0, [2]*100),
    hr = ModbusSequentialDataBlock(0, [3]*100),
    ir = ModbusSequentialDataBlock(0, [4]*100))
context = ModbusServerContext(slaves=store, single=True)

temperature = 0
humidity = 0
heartbit = 0
register_GPIO_INPUT = 0x00
register_GPIO_OUTPUT = 0x02

#---------------------------------------------------------------------------# 
# initialize the server information
#---------------------------------------------------------------------------# 
identity = ModbusDeviceIdentification()
identity.VendorName  = 'pymodbus'
identity.ProductCode = 'PM'
identity.VendorUrl   = 'http://github.com/bashwork/pymodbus/'
identity.ProductName = 'pymodbus Server'
identity.ModelName   = 'pymodbus Server'
identity.MajorMinorRevision = '1.0'

#---------------------------------------------------------------------------# 
# DHT11 thread
#---------------------------------------------------------------------------# 
thread_DHT11 = Thread(target=updating_writer_DHT11, args=())
thread_DHT11.daemon = True
thread_DHT11.start()

#---------------------------------------------------------------------------# 
# Heartbit thread
#---------------------------------------------------------------------------# 
thread_Heartbit = Thread(target=updating_writer_Heartbit, args=())
thread_Heartbit.daemon = True
thread_Heartbit.start()

#---------------------------------------------------------------------------# 
# GPIO thread
#---------------------------------------------------------------------------# 
thread_GPIO = Thread(target=updating_writer_GPIO, args=())
thread_GPIO.daemon = True
thread_GPIO.start()

#---------------------------------------------------------------------------# 
# Main loop
#---------------------------------------------------------------------------# 
time = 0.5 # 3 seconds delay
loop = LoopingCall(f=updating_writer, a=(context,))
loop.start(time, now=False) # initially delay by time

#---------------------------------------------------------------------------# 
# start the Modbus server
#---------------------------------------------------------------------------# 
StartTcpServer(context, identity=identity, address=("IP ADRESS", 502))          # << ========== enter your raspberry pi ip adress




