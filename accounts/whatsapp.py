from __future__ import annotations

import json
import logging
import re
from urllib import error, request

from django.conf import settings
from django.utils import timezone


logger = logging.getLogger(__name__)

WAPI_SUCCESS_STATUSES = {'success', 'sent', 'ok', 'queued'}
DEFAULT_WAPI_BASE_URL = 'https://api.w-api.app/v1'
DEFAULT_TEMPLATE_MESSAGES = {
    'registrations': (
        'Nova atualização de inscrições - Missão Andrews\n'
        'Data/Hora: {data_hora}\n'
        'Total de inscritos: {total_inscritos}\n'
        'Mensagem: {mensagem}'
    ),
    'financial': (
        'Atualização financeira - Missão Andrews\n'
        'Data/Hora: {data_hora}\n'
        'Mensagem: {mensagem}'
    ),
    'documentation': (
        'Ola, {missionario}!\n'
        'Identificamos que ainda falta anexar a seguinte documentacao: {documentos_pendentes}.\n'
        '{mensagem}\n'
        'Acesse para enviar: {link_documentacao}'
    ),
    'general': (
        'Aviso Missão Andrews\n'
        'Data/Hora: {data_hora}\n'
        '{mensagem}'
    ),
    'test': (
        'Teste de WhatsApp - Missão Andrews\n'
        'Enviado por: {usuario}\n'
        'Data/Hora: {data_hora}'
    ),
}
LEGACY_DOCUMENTATION_TEMPLATE_MESSAGES = {
    (
        'Atualização de documentação - Missão Andrews\n'
        'Data/Hora: {data_hora}\n'
        'Mensagem: {mensagem}'
    ),
}


def _clean(value: str) -> str:
    return (value or '').strip()


def _cfg():
    from .models import WhatsAppConfig

    return WhatsAppConfig.objects.filter(pk=1).first()


def _get(field: str, setting_name: str, default='') -> str:
    cfg = _cfg()
    if cfg is not None:
        db_value = _clean(str(getattr(cfg, field, '') or ''))
        if db_value:
            return db_value
    return _clean(str(getattr(settings, setting_name, default) or default))


def _get_bool(field: str, setting_name: str, default: bool) -> bool:
    cfg = _cfg()
    if cfg is not None:
        return bool(getattr(cfg, field, default))
    return bool(getattr(settings, setting_name, default))


def _wapi_configured() -> bool:
    return bool(_get('wapi_token', 'WAPI_TOKEN') and _get('wapi_instance', 'WAPI_INSTANCE'))


def _webhook_configured() -> bool:
    return bool(_get('webhook_url', 'WHATSAPP_WEBHOOK_URL'))


def active_provider() -> str:
    configured = _get('provider', 'WHATSAPP_PROVIDER').lower()
    if configured in {'wapi', 'webhook'}:
        return configured
    if _wapi_configured():
        return 'wapi'
    if _webhook_configured():
        return 'webhook'
    return ''


def notifications_enabled() -> bool:
    return bool(
        _get_bool('notifications_enabled', 'WHATSAPP_NOTIFICATIONS_ENABLED', False)
        and active_provider()
    )


def normalize_phone_number(raw_phone):
    if not raw_phone:
        return ''
    digits = re.sub(r'\D', '', raw_phone)
    if not digits:
        return ''
    if digits.startswith('00'):
        digits = digits[2:]
    if digits.startswith('55'):
        local = digits[2:]
    else:
        local = digits

    local = local.lstrip('0')
    if len(local) > 11:
        local = local[-11:]
    if len(local) == 10:
        local = f'{local[:2]}9{local[2:]}'
    if len(local) not in (10, 11):
        return ''
    return f'55{local}'


def resolve_user_phone(user):
    preference = getattr(user, 'whatsapp_recipient_preference', None)
    if preference and preference.phone_number:
        return preference.phone_number

    registration = getattr(user, 'registration', None)
    if registration is not None:
        volunteer = registration.volunteers.order_by('created_at').first()
        if volunteer is not None:
            return volunteer.phone

    return ''


def _normalize_timeout(timeout: float | tuple[float, float] | int) -> float | int:
    if isinstance(timeout, tuple):
        values = [float(item) for item in timeout if item is not None]
        return max(values) if values else 10.0
    return timeout


def _post_json(url: str, payload: dict, headers: dict[str, str], timeout: float | tuple[float, float] | int) -> tuple[int, dict | None]:
    data = json.dumps(payload).encode('utf-8')
    req = request.Request(url, data=data, headers=headers, method='POST')
    with request.urlopen(req, timeout=_normalize_timeout(timeout)) as response:
        status_code = getattr(response, 'status', None) or response.getcode()
        raw = response.read()
    if not raw:
        return int(status_code), None
    try:
        return int(status_code), json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return int(status_code), None


def send_message(message: str, sent_by: str = '') -> tuple[bool, str]:
    if not _get('group_jid', 'WHATSAPP_GROUP_JID'):
        return False, 'JID do grupo nao configurado.'
    return send_message_to_phone(_get('group_jid', 'WHATSAPP_GROUP_JID'), message, sent_by=sent_by)


def send_message_to_phone(phone_number: str, message: str, sent_by: str = '') -> tuple[bool, str]:
    provider = active_provider()
    message = _clean(message)
    phone_number = _clean(phone_number)

    if not message:
        return False, 'Informe a mensagem.'
    if not provider:
        return False, 'Nenhum provider configurado (W-API ou Webhook).'
    if not phone_number:
        return False, 'Número WhatsApp não configurado.'
    if not notifications_enabled():
        return False, 'Notificacoes de WhatsApp estao desativadas.'

    try:
        if provider == 'wapi':
            return _send_wapi(phone_number, message)
        if provider == 'webhook':
            return _send_webhook(phone_number, message, sent_by=sent_by)
    except (error.HTTPError, error.URLError, TimeoutError, ValueError) as exc:
        logger.warning('Falha ao enviar notificacao WhatsApp via %s: %s', provider, exc)
        return False, str(exc)

    return False, 'Provider desconhecido.'


def send_test_message(sent_by: str = '') -> tuple[bool, str]:
    label = _clean(sent_by) or 'sistema'
    return send_message(
        f'Teste de notificacao enviado por {label}. Configuracao de WhatsApp funcionando.',
        sent_by=label,
    )


def render_message(template, payload):
    class SafePayload(dict):
        def __missing__(self, key):
            return ''

    base = (template or '').strip()
    safe_payload = SafePayload({
        key: '' if value is None else value
        for key, value in (payload or {}).items()
    })
    try:
        return base.format_map(safe_payload)
    except Exception:
        return base


def get_template_message(notification_type):
    from .models import WhatsAppTemplate

    default_message = DEFAULT_TEMPLATE_MESSAGES.get(notification_type, DEFAULT_TEMPLATE_MESSAGES['general'])
    template, _ = WhatsAppTemplate.objects.get_or_create(
        notification_type=notification_type,
        defaults={'message_text': default_message},
    )
    if not (template.message_text or '').strip():
        template.message_text = default_message
        template.save(update_fields=['message_text', 'updated_at'])
    return template.message_text


def template_context(sent_by: str = '', message: str = ''):
    from .models import Volunteer

    now = timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')
    return {
        'usuario': _clean(sent_by) or 'sistema',
        'mensagem': message,
        'data_hora': now,
        'total_inscritos': Volunteer.objects.count(),
        'missionario': '',
        'documentos_pendentes': '',
        'link_documentacao': '',
    }


def send_template_notification(notification_type, payload=None, sent_by: str = ''):
    from .models import WhatsAppRecipientPreference

    template_text = get_template_message(notification_type)
    message = render_message(template_text, payload or template_context(sent_by=sent_by))
    recipients = (
        WhatsAppRecipientPreference.objects
        .select_related('user')
        .filter(user__is_active=True)
        .order_by('user__username')
    )
    results = []

    for preference in recipients:
        if not preference.enabled_for(notification_type):
            continue
        phone_number = normalize_phone_number(preference.phone_number or resolve_user_phone(preference.user))
        if not phone_number:
            results.append((preference.user, False, 'Telefone inválido ou ausente.'))
            continue
        ok, error_message = send_message_to_phone(phone_number, message, sent_by=sent_by)
        results.append((preference.user, ok, error_message))

    return results, message


def send_template_to_phone(notification_type, phone_number: str, payload=None, sent_by: str = ''):
    template_text = get_template_message(notification_type)
    message = render_message(template_text, payload or template_context(sent_by=sent_by))
    normalized_phone = normalize_phone_number(phone_number)
    if not normalized_phone:
        return False, 'Telefone inválido ou ausente.', message, ''

    ok, error_message = send_message_to_phone(normalized_phone, message, sent_by=sent_by)
    return ok, error_message, message, normalized_phone


def ensure_default_templates():
    for notification_type in DEFAULT_TEMPLATE_MESSAGES:
        get_template_message(notification_type)

    from .models import WhatsAppTemplate

    documentation_template = WhatsAppTemplate.objects.filter(notification_type='documentation').first()
    if (
        documentation_template
        and (documentation_template.message_text or '').strip() in LEGACY_DOCUMENTATION_TEMPLATE_MESSAGES
    ):
        documentation_template.message_text = DEFAULT_TEMPLATE_MESSAGES['documentation']
        documentation_template.save(update_fields=['message_text', 'updated_at'])


def _send_wapi(phone_number: str, message: str) -> tuple[bool, str]:
    base_url = (
        _get('wapi_base_url', 'WAPI_BASE_URL', DEFAULT_WAPI_BASE_URL).rstrip('/')
        or DEFAULT_WAPI_BASE_URL
    )
    instance = _get('wapi_instance', 'WAPI_INSTANCE')
    token = _get('wapi_token', 'WAPI_TOKEN')
    url = f'{base_url}/message/send-text?instanceId={instance}'
    payload = {
        'token': token,
        'phone': phone_number,
        'message': message,
    }
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    timeout = (
        float(getattr(settings, 'WAPI_SEND_CONNECT_TIMEOUT', 6.0) or 6.0),
        float(getattr(settings, 'WAPI_SEND_READ_TIMEOUT', 20.0) or 20.0),
    )
    status_code, response_data = _post_json(url, payload, headers, timeout)
    if not (200 <= status_code < 300):
        return False, f'W-API retornou status {status_code}.'
    if not isinstance(response_data, dict):
        return True, ''

    status = _clean(str(response_data.get('status') or response_data.get('state') or '')).lower()
    message_id = _clean(str(response_data.get('messageId') or response_data.get('insertedId') or ''))
    if status in WAPI_SUCCESS_STATUSES or message_id:
        return True, ''

    return False, 'W-API retornou uma resposta inesperada.'


def _send_webhook(phone_number: str, message: str, sent_by: str = '') -> tuple[bool, str]:
    headers = {'Content-Type': 'application/json'}
    token = _get('webhook_token', 'WHATSAPP_WEBHOOK_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    payload = {
        'event': 'manual_notification',
        'phone': phone_number,
        'message': message,
        'sent_by': sent_by,
    }
    timeout = int(getattr(settings, 'WHATSAPP_WEBHOOK_TIMEOUT_SECONDS', 10) or 10)
    status_code, _ = _post_json(
        _get('webhook_url', 'WHATSAPP_WEBHOOK_URL'),
        payload,
        headers,
        timeout,
    )
    if not (200 <= status_code < 300):
        return False, f'Webhook retornou status {status_code}.'
    return True, ''
