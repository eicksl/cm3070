import win32gui, win32ui
from win32api import GetSystemMetrics, GetSysColor
from time import time


dc = win32gui.GetDC(0)
dcObj = win32ui.CreateDCFromHandle(dc)
hwnd = win32gui.WindowFromPoint((0,0))
brush = win32ui.CreateBrush()
brush.CreateSolidBrush(GetSysColor(26))
monitor = (0, 0, GetSystemMetrics(0), GetSystemMetrics(1))

start = time()
while True:
    #m = win32gui.GetCursorPos()
    #dcObj.FrameRect((m[0], m[1], m[0]+30, m[1]+30))
    dcObj.FrameRect((718, 104, 875, 167), brush)
    #win32gui.InvalidateRect(hwnd, monitor, True) # Refresh the entire monitor

    if time() - start > 5:
        win32gui.InvalidateRect(hwnd, monitor, True)
        break
