"""Run with the serving environment's Python; preserve string-valued arguments."""
import json
from vllm.tool_parsers.granite4_tool_parser import Granite4ToolParser
from vllm.tool_parsers.hermes_tool_parser import Hermes2ProToolParser

action = {"code": "print('ok')", "reason": "Parser regression check"}
for arguments in (action, json.dumps(action)):
    raw = '<tool_call>\n' + json.dumps({"name": "respond", "arguments": arguments}) + '\n</tool_call>'
    fixed = Granite4ToolParser(object()).extract_tool_calls(raw, None)
    old = Hermes2ProToolParser(object()).extract_tool_calls(raw, None)
    assert fixed.tools_called and len(fixed.tool_calls) == 1
    assert json.loads(fixed.tool_calls[0].function.arguments) == action
    previous = json.loads(old.tool_calls[0].function.arguments)
    assert isinstance(previous, str) if isinstance(arguments, str) else previous == action
    print(type(arguments).__name__, 'Hermes decoded:', type(previous).__name__, 'Granite4 decoded: dict')
