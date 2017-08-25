from copy import copy

import mandrill

from tunga.settings import MANDRILL_API_KEY, DEFAULT_FROM_EMAIL


def get_client():
    return mandrill.Mandrill(MANDRILL_API_KEY)


def create_merge_var(name, value):
    return dict(name=name, content=value)


def send_email(template_name, to, subject=None, merge_vars=None, cc=None, bcc=None):
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
    response = mandrill_client.messages.send_template(template_name, [], message)
    print('mandrill response: ', response)
    return response


general_vars = [
    dict(name="developers_browse_url", content="https://tunga.io/people/filter/developers"),
    dict(name="project_url", content="https://tunga.io/work"),
    dict(name="project_complete_url", content="https://tunga.io/work"),
    dict(name="project_tour_url", content="https://tunga.io/work/"),
    dict(name="project_applications_url", content="https://tunga.io/work/"),
    dict(name="task_url", content="https://tunga.io/work"),
    dict(name="task_complete_url", content="https://tunga.io/work"),
    dict(name="task_tour_url", content="https://tunga.io/work/"),
    dict(name="task_applications_url", content="https://tunga.io/work/"),
    dict(name="work_url", content="https://tunga.io/work"),
    dict(name="work_title", content="Task Title"),
    dict(name="work_applications_url", content="https://tunga.io/work/"),
    dict(name="number_of_applications", content="4"),
]
general_to = [
    dict(email="tdsemakula@gmail.com", type="bcc")
]


def send_generic(template_name, subject=None, external=False):
    to = copy(general_to)
    if external:
        to.append(dict(email="bart@tunga.io"))

    merge_vars = copy(general_vars)
    merge_vars.append(dict(name="first_name", content=external and "Bart" or "David"))

    if subject:
        merge_vars.append(dict(name="subject", content=subject))

    send_email(template_name, to, subject=subject, merge_vars=merge_vars)


def send_1(external=False):
    send_generic('1', 'Welcome to Tunga', external=external)


def send_2(external=False):
    send_generic('2', 'Hiring software developers just got easier', external=external)


def send_7(external=False):
    send_generic('7', "Thanks for posting a project. What's next...", external=external)


def send_9(external=False):
    send_generic('9', "Thanks for posting a task on Tunga. What's next...", external=external)


def send_10(external=False):
    send_generic('10', "Last week you posted work on Tunga", external=external)


def send_11(external=False):
    send_generic('10', "Work is about to expire", external=external)