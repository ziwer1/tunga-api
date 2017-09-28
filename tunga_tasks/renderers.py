# -*- coding: utf-8 -*-

from rest_framework import renderers


class PDFRenderer(renderers.BaseRenderer):
    media_type = 'application/pdf'
    format = 'pdf'

    def render(self, data, media_type=None, renderer_context=None):
        return data.encode(self.charset)
