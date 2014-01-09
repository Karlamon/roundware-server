# from django.views.generic import CreateView
from django.forms.models import (modelformset_factory, BaseModelFormSet,                                  
                                 inlineformset_factory)
from django.core.urlresolvers import reverse

import floppyforms as forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from crispy_forms.utils import render_crispy_form
from braces.views import LoginRequiredMixin
from djangoformsetjs.utils import formset_media_js

from roundware.rw.models import Tag, LocalizedString, Language
from roundware.rw.widgets import NonAdminRelatedFieldWidgetWrapper


class TagCreateForm(forms.ModelForm):
    """ Custom create form for tags allowing batch creation of Tags assigned
        to a TagCategory
    """

    msg_rel = Tag.loc_msg.through

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.template = 'bootstrap3/table_inline_formset.html'
        # self.helper.add_input(Submit('submit', 'Save All'))
        super(TagCreateForm, self).__init__(*args, **kwargs)

    class Meta:
        model = Tag
        fields = ['tag_category']  # formset in multiview adds others
        widgets = {  # floppyforms requires override orig widgets to use theirs
            'tag_category': forms.Select,
            'value': forms.TextInput,
            'description': forms.TextInput,
            'data': forms.TextInput,
            'loc_msg': NonAdminRelatedFieldWidgetWrapper(
                forms.SelectMultiple(), '/admin/rw/localizedstring/add')
        }
        labels = {
            'loc_msg': "Localized Text"
        }

    class Media:
        js = formset_media_js + ('admin/js/admin/RelatedObjectLookups.js',)
        css = {'all': ('rw/css/tag_batch_add.css',)}
      

class BatchTagFormset(BaseModelFormSet):

    def save(self):
        """ saving is handled by view.  May need to revisit this as we 
        add inlines.
        """
        pass

    # XXX TODO: if we decide to add localized messages inline we can use below
    # as a start.
    # def add_fields(self, form, index):
    #     """ add custom fields for entry of localized string text and language.  
    #         Can't use an inlineformset since the field loc_msg is manytomany.
    #     """
    #     super(BatchTagFormset, self).add_fields(form, index)
    #     form.fields["localized_text"] = forms.CharField()
    #     form.fields["loc_txt_language"] = forms.ModelChoiceField(Language.objects.all())


        