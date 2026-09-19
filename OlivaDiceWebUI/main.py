from . import bridge, service


class Event:
    @staticmethod
    def init_after(plugin_event, Proc):
        if 'OlivaDiceCore' not in Proc.get_plugin_list():
            Proc.log(3, 'OlivaDiceWebUI: OlivaDiceCore 未加载，插件页面暂不可用')
            return
        Proc.log(2, 'OlivaDiceWebUI: 已接入 OlivOS WebUI 插件页面')

    @staticmethod
    def save(plugin_event, Proc):
        bridge.clear_transfers()

    @staticmethod
    def menu(plugin_event, Proc):
        if getattr(plugin_event.data, 'namespace', None) != 'OlivaDiceWebUI':
            return
        context = getattr(plugin_event.data, 'webui', None)
        if not isinstance(context, dict):
            return
        request_id = context.get('request_id')
        if not isinstance(request_id, str) or not request_id or len(request_id) > 128:
            return
        try:
            result = bridge.dispatch(
                Proc,
                getattr(plugin_event.data, 'event', None),
                getattr(plugin_event.data, 'payload', None),
                context,
            )
            response = {'ok': True, 'result': result}
        except (service.InvalidInput, ValueError, UnicodeDecodeError) as exc:
            response = {'ok': False, 'error': str(exc)}
        except Exception as exc:
            Proc.log(4, 'OlivaDiceWebUI: WebUI 请求处理失败: {}'.format(exc))
            response = {'ok': False, 'error': '处理失败，请查看 OlivOS 日志'}
        plugin_event.send('webui', request_id, response)
