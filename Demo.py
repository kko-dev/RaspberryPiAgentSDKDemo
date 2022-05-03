import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
import os
import tvagentapi
import threading
import time

cond = threading.Condition()
approved= False
connected = False

STATUS_LED = 3
PARTICIPENT_1 = 16
PARTICIPENT_2 = 18
HELP_BUTTON = 10
APPROVE = 35
REJECT = 37
TERMINATE_ALL = 40

def approve_button_callback(channel):
    print("approve Button was pushed was pushed!")
    global approved, cond
    approved = True
    cond.acquire()
    cond.notify()
    cond.release()

def reject_button_callback(channel):
    print("reject Button was pushed was pushed!")
    global approved, cond
    approved = False
    cond.acquire()
    cond.notify()
    cond.release()

def terminate_button_callback(channel, s_module):
    print(f"terminate all ongoing TeamViewer sessions")
    s_module.terminateTeamViewerSessions()

def connectionStatusChanged(status, is_module):
    global connected, STATUS_LED
    print(f"[IAgentConnection] Status: {status}")
    if status == tvagentapi.AgentConnection.Status.Connected:
        GPIO.output(STATUS_LED, 1)
        connected = True
    else:
        GPIO.output(STATUS_LED, 0)
        connected = False

def requestSupportCase():
    global connection
    global connected, approved, cond
    instant_support_module = connection.getModule(tvagentapi.ModuleType.InstantSupport)
    approved = False
    cond = threading.Condition()
    if not connected:
        print("Can not request instant supprot as there no agent connection")
        return;
    request_data = {
    'accessToken': '',
    'name': "Help Me Please!",
    'group': "Contacts",
    'description': "I need your support!",
    'email': "supporter@teamviewer.com",
    'sessionCode': os.environ['TV_SESSION_CODE'] if 'TV_SESSION_CODE' in os.environ else ""
    }
    print("\tRequesting instant support... " + str(request_data))
    instant_support_module.requestInstantSupport(request_data)

def support_button_callback(channel):
    print("Support Button was pushed was pushed!")
    requestSupportCase()

def instantSupportSessionDataChanged(new_data):
    if new_data['state'] == tvagentapi.InstantSupportModule.SessionState.Undefined:
        output = "no session data"
    else:
        output = str(new_data)
        print(f"[IInstantSupportModule] instantSupportSessionDataChanged: {output}")


def instantSupportRequestError(error_code):
    print(f"[IInstantSupportModule] instantSupportRequestError: {error_code}")

def instantSupportConnectionRequested(is_module):
    global approved, cond, STATUS_LED
    counter = 0
    maxCounter = 10
    cond.acquire()
    while counter <=maxCounter:
        ++counter
        time.sleep(1)
        GPIO.output(STATUS_LED, 0)
        val = cond.wait(1)
        GPIO.output(STATUS_LED, 1)
        if val:
            print("something was pressed, checking...")
            if approved:
                print("connection approved")
                is_module.acceptConnectionRequest()
                break;
            else:
                print("connection rejected")
                is_module.rejectConnectionRequest()
            break;
        break
        else:
            print("nothing was pressed yet, signaling...")
    cond.release()
    if counter == maxCounter:
        print("Timeout reached")
        is_module.timeoutConnectionRequest()

def print_running_sessions(tvsm_module):
    running_sessions = tvsm_module.getRunningSessions()
    print(f"[TVSessionManagement]: Running sessions {running_sessions}")

def session_state_changed(tvsm_module, started, session_id, sessions_count):
    print(f"[TVSessionManagement] Session {'started' if started else 'stopped'}")
    print(f"[TVSessionManagement] Session ID: {session_id}, sessions count: {sessions_count}")
    print_running_sessions(tvsm_module)
    if sessions_count == 0:
        GPIO.output(PARTICIPENT_1, 0)
        GPIO.output(18, 0)
    if sessions_count == 1:
        GPIO.output(PARTICIPENT_1, 1)
        GPIO.output(18, 0)
    if sessions_count == 2:
        GPIO.output(PARTICIPENT_1, 1)
        GPIO.output(18, 1)


GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)

GPIO.setup(STATUS_LED, GPIO.OUT)
GPIO.setup(PARTICIPENT_1, GPIO.OUT)
GPIO.setup(PARTICIPENT_2, GPIO.OUT)
GPIO.output(STATUS_LED, 0)
GPIO.output(PARTICIPENT_1, 0)
GPIO.output(PARTICIPENT_2, 0)

GPIO.setup(HELP_BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Set pin 10 to be an input pin and set initial value to be pulled low (off)
GPIO.add_event_detect(HELP_BUTTON,GPIO.RISING,callback=support_button_callback) # Setup event on pin 10 rising edge

GPIO.setup(APPROVE, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Set pin 10 to be an input pin and set initial value to be pulled low (off)
GPIO.add_event_detect(APPROVE,GPIO.RISING,callback=approve_button_callback) # Setup event on pin 10 rising edge

GPIO.setup(REJECT, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Set pin 10 to be an input pin and set initial value to be pulled low (off)
GPIO.add_event_detect(REJECT,GPIO.RISING,callback=reject_button_callback) # Setup event on pin 10 rising edge

GPIO.setup(TERMINATE_ALL, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Set pin 10 to be an input pin and set initial value to be pulled low (off)
GPIO.add_event_detect(TERMINATE_ALL,GPIO.RISING,callback=lambda channel: terminate_button_callback(channel, tv_session_management)) # Setup event on pin 10 rising edge


api = tvagentapi.TVAgentAPI()

connection = api.createAgentConnectionLocal()
instant_support_module = connection.getModule(tvagentapi.ModuleType.InstantSupport)

if not instant_support_module.isSupported():
    raise RuntimeError("InstantSupportModule not supported")

connection.setStatusChangedCallback(lambda status: connectionStatusChanged(status, instant_support_module))
instant_support_module.setCallbacks({
    'sessionDataChangedCallback': instantSupportSessionDataChanged,
    'requestErrorCallback': instantSupportRequestError,
    'connectionRequestCallback': lambda: instantSupportConnectionRequested(instant_support_module)
})

tv_session_management = connection.getModule(tvagentapi.ModuleType.TVSessionManagement)
if not tv_session_management.isSupported():
    raise RuntimeError("TVSessionManagementModule not supported")

tv_session_management.setCallbacks({
    'sessionStartedCallback': lambda sid, s_cnt:
    session_state_changed(tv_session_management, True, sid, s_cnt),
    'sessionStoppedCallback': lambda sid, s_cnt:
    session_state_changed(tv_session_management, False, sid, s_cnt)
})

print("Connecting to IoT Agent...")
connection.start()

print("Press Ctrl+C to exit")
    while True:
    try:
        connection.processEvents(waitForMoreEvents=True, timeoutMs=100)
    except KeyboardInterrupt:
        break

GPIO.cleanup() # Clean up
