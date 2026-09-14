"""Constants for the PowerShades protocol."""

UDP_PORT = 42
BROADCAST_IP = "255.255.255.255"

# Protocol opcodes
OP_GET_SERIAL = 0x00
OP_SET_LIMIT = 0x01
OP_JOG_UP = 0x03
OP_JOG_DOWN = 0x04
OP_JOG_STOP = 0x05
OP_INDICATE = 0x08
OP_REBOOT = 0x18
OP_SET_POSITION = 0x1A
OP_GET_STATUS = 0x1D
OP_CLEAR_LIMITS = 0x1E
OP_SAVE_LIMITS = 0x1F
OP_STEP_UP = 0x23
OP_STEP_DOWN = 0x24
OP_GET_DEBUG_INFO = 0x26
OP_POE_MOTOR_PARAMS = 0x27
OP_GET_DEVICE_ID = 0x2E
OP_GET_SHADE_NAME = 0x34
OP_DISABLES = 0x35
OP_GET_DEVICE_NAME = 0x3A
OP_ADMIN_ACCESS = 0x3C
OP_JSON_TEST = 0x40
OP_CLOUD_UPDATE = 0x44

# Limit types
LIMIT_UPPER = 0x0000
LIMIT_LOWER = 0x0001

# Model byte in the Get Serial Number reply
MODEL_POE_SHADE = 1
MODEL_RF_GATEWAY = 100

MODEL_NAMES = {
    MODEL_POE_SHADE: "PoE Shade",
    MODEL_RF_GATEWAY: "RF Gateway",
}

# PoEErrorCode - the values found in Get Debug Info's ErrorList field.
# Confirmed against PowershadesCommon's PoEErrorCode enum and how
# PowershadesConfig.NET's frmTest.cs decodes ErrorList (ASCII decimal
# numbers, comma-separated) into this same 1-33 mapping.
POE_ERROR_CODES = {
    1: "Motor_Stall",
    2: "Motor_Stop_Function",
    3: "Active_Motor_Stop_Function",
    4: "TCP_CRC_Mismatch",
    5: "TCP_Firmware_Update",
    6: "Reboot_Function",
    7: "Motor_Over_Current",
    8: "Flash_Save_Function",
    9: "TCP_Keep_Alive",
    10: "TCP_Key_Exchange",
    11: "TCP_Get_ID",
    12: "TCP_Get_Status",
    13: "TCP_Set_Clock",
    14: "TCP_Erase_Schedules",
    15: "TCP_Add_Schedule",
    16: "TCP_Set_Position",
    17: "TCP_Save_Position",
    18: "TCP_Recall_Position",
    19: "TCP_Reboot",
    20: "TCP_Set_Timeout",
    21: "Enter_Sleep_Mode",
    22: "Exit_Sleep_Mode",
    23: "Battery_Low_Power_Down",
    24: "ETH_RX_Overflow",
    25: "ETH_TX_Overflow",
    26: "DNS_Timer_Expired",
    27: "DNS_Not_Bound",
    28: "Host_Timeout",
    29: "TCP_Send_Failed",
    30: "RX_Length_Mismatch",
    31: "Send_Timer_Expired",
    32: "Motor_Fight_Back_Function",
    33: "Erasing_Flash_Memory",
}

# Feature Disables (op 0x35) bit for TCP/cloud connectivity. Confirmed
# against PowershadesConfig.NET's frmMotorConfigV2.cs (chkBoxTCPCloud
# maps to bit 6 of DisablesByte via .NET BitArray, LSB-first).
DISABLE_TCP_CLOUD = 0x40

# Admin Access (op 0x3C) key. A fixed constant baked into every copy of
# the vendor's app - not real authentication, gates privileged commands
# like PoE Motor Parameters. Must be sent immediately before the
# privileged command, as an atomic pair.
ADMIN_ACCESS_KEY = 179097173

# Timing
DISCOVERY_TIMEOUT = 3.0
REQUEST_TIMEOUT = 2.0
REQUEST_RETRIES = 2
