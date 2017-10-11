# -*- coding: utf-8 -*-

from copy import copy

from django.db.models.query_utils import Q
from django.template.loader import render_to_string
from django_rq.decorators import job
from weasyprint import HTML

from tunga_profiles.models import DeveloperNumber
from tunga_tasks.models import Task
from tunga_tasks.tasks import generate_invoice_number
from tunga_utils.serializers import InvoiceUserSerializer, TaskInvoiceSerializer


@job
def process_invoices(pk, invoice_types=('client',), user_id=None, is_admin=False, filepath=None):
    all_invoices = list()

    if pk == 'all':
        tasks = Task.objects.filter(closed=True, taskinvoice__isnull=False)
        if user_id and not is_admin:
            tasks = tasks.filter(
                Q(user_id=user_id) | Q(owner_id=user_id) | Q(pm_id=user_id) | Q(participant_id=user_id))
        tasks = tasks.distinct()
    else:
        tasks = Task.objects.filter(id=pk)

    for task in tasks:
        invoice = task.invoice
        if invoice:
            if not invoice.number:
                try:
                    invoice = generate_invoice_number(invoice)
                except:
                    pass

            if invoice.number:
                initial_invoice_data = TaskInvoiceSerializer(invoice).data
                initial_invoice_data['date'] = task.invoice.created_at.strftime('%d %B %Y')

                task_owner = task.user
                if task.owner:
                    task_owner = task.owner

                participation_shares = task.get_participation_shares()
                common_developer_info = list()
                for share_info in participation_shares:
                    participant = share_info['participant']
                    developer, created = DeveloperNumber.objects.get_or_create(user=participant.user)

                    amount_details = invoice.get_amount_details(share=share_info['share'])

                    common_developer_info.append({
                        'developer': InvoiceUserSerializer(participant.user).data,
                        'amount': amount_details,
                        'dev_number': developer.number or ''
                    })

                for invoice_type in invoice_types:
                    task_developers = []
                    invoice_data = copy(initial_invoice_data)

                    if invoice_type == 'client':
                        invoice_data['number_client'] = '{}C'.format(invoice_data['number'])
                        task_developers = [dict()]
                    else:
                        for common_info in common_developer_info:
                            final_dev_info = copy(common_info)
                            final_dev_info['number'] = '{}{}{}'.format(
                                invoice_data['number'],
                                invoice_type != 'client' and common_info['dev_number'] or '',
                                (invoice_type == 'developer' and 'D' or (invoice_type == 'tunga' and 'T' or 'C'))
                            )
                            task_developers.append(final_dev_info)

                    invoice_data['developers'] = task_developers

                    client_country = None
                    if invoice_type == 'client' and task_owner.profile and \
                            task_owner.profile.country and task_owner.profile.country.code:
                        client_country = task_owner.profile.country.code

                    if client_country == 'NL':
                        invoice_location = 'NL'
                    elif client_country in [
                        # EU members
                        'BE', 'BG', 'CZ', 'DK', 'DE', 'EE', 'IE', 'EL', 'ES', 'FR', 'HR', 'IT', 'CY', 'LV', 'LT', 'LU',
                        'HU', 'MT', 'AT', 'PL', 'PT', 'RO', 'SI', 'SK', 'FI', 'SE', 'UK'
                        # European Free Trade Association (EFTA)
                                                                                    'IS', 'LI', 'NO', 'CH'
                    ]:
                        invoice_location = 'europe'
                    else:
                        invoice_location = 'world'

                    all_invoices.append(
                        dict(
                            invoice_type=invoice_type,
                            invoice=invoice_data, location=invoice_location
                        )
                    )
    ctx = dict(
        invoices=all_invoices
    )

    rendered_html = render_to_string("tunga/pdf/invoice.html", context=ctx).encode(encoding="UTF-8")
    if filepath:
        HTML(string=rendered_html, encoding='utf-8').write_pdf(filepath)
    return rendered_html
