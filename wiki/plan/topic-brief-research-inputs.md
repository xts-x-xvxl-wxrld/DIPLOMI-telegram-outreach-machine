# Topic Brief Research Inputs

## Goal

Keep topic-brief and style-rule authoring permissive for research workflows so operators can store
any guidance or example text during setup without bot-side or backend authoring-time rejection.

## Scope

- remove draft-brief wizard text blocking during topic creation
- remove backend topic/style-rule authoring validation that rejects specific operator wording
- keep existing downstream reply-generation and approval constraints unchanged

## Acceptance

- `Add engagement` -> `Create topic` accepts arbitrary operator text in guidance/example fields
- direct topic-example additions and style-rule saves accept the same unrestricted text
- existing topic create/edit flows still preserve required-field and deduplication behavior
- downstream send/draft safety rules remain unchanged
