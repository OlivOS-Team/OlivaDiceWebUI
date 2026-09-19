import webbrowser

from . import server


def _local_url():
    """Browser URL for the menu entry.

    The default bind is 0.0.0.0, which is not a navigable address, so a wildcard
    listener is opened through loopback while an explicit bind is used verbatim.
    """
    bind = server.BIND_HOST
    if server.BIND_IS_LOOPBACK:
        host = bind
    elif bind == '0.0.0.0':
        host = '127.0.0.1'
    else:
        host = bind
    return 'http://{}:{}/'.format(host, server.PORT)


class Event:
    @staticmethod
    def init_after(plugin_event, Proc):
        if 'OlivaDiceCore' not in Proc.get_plugin_list():
            Proc.log(3, 'OlivaDiceWebUIStandalone: OlivaDiceCore 未加载，WebUI 不启动')
            return
        if server.STARTUP_NETWORK_WARNING:
            Proc.log(4, 'OlivaDiceWebUIStandalone: {}'.format(server.STARTUP_NETWORK_WARNING))
        try:
            server.start(Proc)
        except Exception as exc:
            # A failed listener must not abort OlivOS' whole plugin load pass.
            Proc.log(4, 'OlivaDiceWebUIStandalone: 服务启动失败: {}'.format(exc))
    @staticmethod
    def save(plugin_event, Proc):
        server.stop()

    @staticmethod
    def menu(plugin_event, Proc):
        if plugin_event.data.event == 'OlivaDiceWebUIStandalone_001':
            url = _local_url()
            try:
                if not webbrowser.open(url):
                    Proc.log(2, 'OlivaDiceWebUIStandalone: 请在本机浏览器打开 ' + url)
            except webbrowser.Error:
                Proc.log(2, 'OlivaDiceWebUIStandalone: 请在本机浏览器打开 ' + url)
