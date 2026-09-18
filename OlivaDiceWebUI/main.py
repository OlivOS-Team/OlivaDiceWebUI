import webbrowser

import OlivaDiceWebUI.server


class Event:
    @staticmethod
    def init_after(plugin_event, Proc):
        if 'OlivaDiceCore' not in Proc.get_plugin_list():
            Proc.log(3, 'OlivaDiceWebUI: OlivaDiceCore 未加载，WebUI 不启动')
            return
        OlivaDiceWebUI.server.start(Proc)

    @staticmethod
    def save(plugin_event, Proc):
        OlivaDiceWebUI.server.stop()

    @staticmethod
    def menu(plugin_event, Proc):
        if plugin_event.data.event == 'OlivaDiceWebUI_001':
            url = 'http://127.0.0.1:{}/'.format(OlivaDiceWebUI.server.PORT)
            try:
                if not webbrowser.open(url):
                    Proc.log(2, 'OlivaDiceWebUI: 请在本机浏览器打开 ' + url)
            except webbrowser.Error:
                Proc.log(2, 'OlivaDiceWebUI: 请在本机浏览器打开 ' + url)
