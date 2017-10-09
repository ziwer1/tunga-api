# -*- coding: utf-8 -*-

from time import sleep

import mandrill
from django_rq import job

from tunga.settings import MANDRILL_API_KEY, DEFAULT_FROM_EMAIL
from tunga_utils.helpers import convert_to_text
from tunga_utils.hubspot_utils import create_hubspot_engagement


def get_client():
    return mandrill.Mandrill(MANDRILL_API_KEY)


def create_merge_var(name, value):
    return dict(name=name, content=value)


def send_email(template_name, to, subject=None, merge_vars=None, cc=None, bcc=None, attachments=None):
    mandrill_client = get_client()

    final_to = []
    if isinstance(to, (str, unicode)):
        final_to.append(dict(email=to))
    else:
        for email in to:
            final_to.append(dict(email=email))

    if cc:
        for email in cc:
            final_to.append(dict(email=email, type='cc'))
    if bcc:
        for email in bcc:
            final_to.append(dict(email=email, type='bcc'))

    message = dict(
        from_email=DEFAULT_FROM_EMAIL,
        from_name='Tunga',
        to=final_to,
        subject=subject,
        global_merge_vars=merge_vars,
        merge=True,
    )
    if subject:
        message['subject'] = '[Tunga] {}'.format(subject)
    if attachments:
        message['attachments'] = attachments
    responses = mandrill_client.messages.send_template(template_name, [], message)
    return responses


@job
def log_emails(responses, to, subject=None, cc=None, bcc=None, deal_ids=None):
    mandrill_client = get_client()

    print('logging responses: ', responses)

    if responses:
        for response in responses:
            content_id = response.get('_id')
            print('mandrill response', content_id, response)

            if response.get('status') == 'sent':
                tries = 0
                while True:
                    try:
                        sent_details = mandrill_client.messages.content(content_id)
                    except mandrill.UnknownMessageError:
                        sent_details = None

                    print('sent_details', sent_details)
                    if sent_details:
                        email_html = sent_details.get('html', '')
                        email_text = sent_details.get('text', '')

                        create_hubspot_engagement(
                            from_email=sent_details.get('from_email', DEFAULT_FROM_EMAIL),
                            to_emails=isinstance(to, (str, unicode)) and [to] or to,
                            subject=sent_details.get('subject', subject),
                            body=email_text or convert_to_text(email_html),
                            **dict(cc=cc, bcc=bcc, html=email_html, deal_ids=deal_ids)
                        )
                        break
                    else:
                        # Hacks to wait to Mandrill indicates the message so it can be logged in hubspot
                        tries += 1
                        if tries >= 60:
                            # Give up after for 15 minutes
                            break
                        else:
                            # Wait for 15 seconds
                            sleep(15)


