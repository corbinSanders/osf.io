<%inherit file="notify_base.mako" />

<%def name="content()">
<tr>
  <td style="border-collapse: collapse;">
    <%!
        from website import settings
    %>
        Dear ${contributor.fullname},<br>
        <br>
    % if not ever_public:
        % if is_requester:
            You have withdrawn your ${document_type} <a href="${reviewable.absolute_url}">"${reviewable.title}"</a> from ${reviewable.provider.name}.
            <br>
            The ${document_type} has been removed from ${reviewable.provider.name}.
            <br>
        % else:
            ${requester.fullname} has withdrawn your ${document_type} <a href="${reviewable.absolute_url}">"${reviewable.title}"</a> from ${reviewable.provider.name}. ${requester.fullname} provided the following justification: "${reviewable.withdrawal_justification}"
            <br>
            The ${document_type} has been removed from ${reviewable.provider.name}.
            <br>
        % endif
    % else:
        % if is_requester:
            Your request to withdraw your ${document_type} <a href="${reviewable.absolute_url}">"${reviewable.title}"</a> from ${reviewable.provider.name} has been approved by the service moderators.
            <br>
            The ${document_type} has been removed from ${reviewable.provider.name}, but its metadata is still available: title of the withdrawn ${document_type}, its contributor list, abstract, tags, DOI, and reason for withdrawal (if provided).
            <br>
        % elif force_withdrawal:
            A moderator has withdrawn your ${document_type} <a href="${reviewable.absolute_url}">"${reviewable.title}"</a> from ${reviewable.provider.name}.
            <br>
            The ${document_type} has been removed from ${reviewable.provider.name}, but its metadata is still available: title of the withdrawn ${document_type}, its contributor list, abstract, tags, and DOI. The moderator has provided the following justification: "${reviewable.withdrawal_justification}".
            <br>
        % else:
            ${requester.fullname} has withdrawn your ${document_type} <a href="${reviewable.absolute_url}">"${reviewable.title}"</a> from ${reviewable.provider.name}.
            <br>
            The ${document_type} has been removed from ${reviewable.provider.name}, but its metadata is still available: title of the withdrawn ${document_type}, its contributor list, abstract, tags, and DOI. ${requester.fullname} provided the following justification: "${reviewable.withdrawal_justification}".
            <br>
        % endif
    % endif
        <br>
        Sincerely,<br>
        The ${reviewable.provider.name} and OSF Teams
        <br>

</tr>
</%def>
