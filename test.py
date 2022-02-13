from win32gui import GetDC, WindowFromPoint, InvalidateRect
from win32ui import CreateDCFromHandle, CreateBrush
from win32api import GetSystemMetrics, GetSysColor
from pyWinhook import HookManager
import ctypes


class Draw_Screen_Rect:
    def __init__(self):
        self.pos = [0, 0, 0, 0]
        dc = GetDC(0)
        self.dcObj = CreateDCFromHandle(dc)
        self.hwnd = WindowFromPoint((0,0))
        self.monitor = (0, 0, GetSystemMetrics(0), GetSystemMetrics(1))
        self.clicked = False
        self.b1 = CreateBrush()
        self.b1.CreateSolidBrush(GetSysColor(255))
        self.final_rect = None
        self.refresh_frames = 0
        self.refresh_after = 10


    def _draw_rect_func(self):
        self.dcObj.FrameRect(tuple(self.pos), self.b1)


    def _refresh_rect(self):
        InvalidateRect(self.hwnd, self.monitor, True)
    

    def _OnMouseEvent(self, event):
        if event.Message == 513:
            self.clicked = True
            self.pos[0], self.pos[1] = event.Position
        elif event.Message == 514:
            self.clicked = False
            self.pos[2], self.pos[3] = event.Position
            self._draw_rect_func()
            self._refresh_rect()
            self.final_rect = self.pos
            self._destroy_hooks()
        elif event.Message == 512:
            if self.clicked:
                self.pos[2], self.pos[3] = event.Position
                if self.refresh_frames % 2 == 0:
                    self._draw_rect_func()
                self.refresh_frames += 1
                if self.refresh_frames > self.refresh_after:
                    self.refresh_frames = 0
                    self._refresh_rect()
        return True


    def create_hooks(self):
        self.hm = HookManager()
        self.hm.MouseLeftDown = self._OnMouseEvent
        self.hm.MouseLeftUp = self._OnMouseEvent
        self.hm.MouseMove = self._OnMouseEvent
        self.hm.HookMouse()
        self.hm.HookKeyboard()


    def _destroy_hooks(self):
        self.hm.UnhookMouse()
        ctypes.windll.user32.PostQuitMessage(0)


    def output(self):
        return self.final_rect



if __name__ == '__main__':
    app = Draw_Screen_Rect()
    app.create_hooks()
    from pythoncom import PumpMessages
    PumpMessages()
    out = app.output()
    print(out)
