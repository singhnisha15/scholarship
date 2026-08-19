from allauth.account.adapter import DefaultAccountAdapter


class ScholarshipAccountAdapter(DefaultAccountAdapter):

    def add_message(
        self,
        request,
        level,
        message_template,
        context=None,
        extra_tags="",
    ):
        # Suppress allauth's automatic login/logout messages.
        if message_template in {
            "account/messages/logged_in.txt",
            "account/messages/logged_out.txt",
        }:
            return

        # Keep all other allauth messages working normally.
        return super().add_message(
            request,
            level,
            message_template,
            context=context,
            extra_tags=extra_tags,
        )