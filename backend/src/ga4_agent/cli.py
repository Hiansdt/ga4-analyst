"""Terminal chat with the agent. Run: uv run --env-file ../.env ga4-agent"""

from ga4_agent.bootstrap import build_agent
from ga4_agent.config import Settings
from ga4_agent.events import Event, TextDelta, ToolFinished, ToolStarted, TurnCompleted, TurnFailed

DIM, RED, RESET = "\033[2m", "\033[31m", "\033[0m"


def main() -> None:
    agent = build_agent(Settings())
    history: list[dict] = []
    print("Ask about the Google Merchandise Store (Nov 2020 to Jan 2021). Ctrl+D to quit.")
    while True:
        try:
            question = input("\nyou> ").strip()
        except EOFError:
            return
        if not question:
            continue
        for event in agent.run_turn(history, question):
            render(event)
            if isinstance(event, TurnCompleted):
                history += event.messages
        print()


def render(event: Event) -> None:
    match event:
        case TextDelta(text):
            print(text, end="", flush=True)
        case ToolStarted(name="run_sql", input=tool_input):
            sql = tool_input.get("sql", "").strip().replace("\n", "\n    ")
            print(f"\n{DIM}  running SQL:\n    {sql}{RESET}")
        case ToolStarted(name="query_metrics", input=tool_input):
            print(f"\n{DIM}  querying metrics: {tool_input}{RESET}")
        case ToolStarted(name=name):
            print(f"\n{DIM}  calling {name}{RESET}")
        case ToolFinished(is_error=True, display=display):
            print(f"{RED}  failed: {display.get('error')}{RESET}")
        case ToolFinished(name="suggest_follow_ups", display=suggestions):
            print(f"{DIM}  suggested: {' | '.join(suggestions['questions'])}{RESET}")
        case ToolFinished(name="create_chart", display=chart):
            print(f"{DIM}  [{chart['type']} chart: {chart['title']} ({len(chart['rows'])} points)]{RESET}\n")
        case ToolFinished(display=display):
            if "total_rows" in display:
                print(f"{DIM}  -> {display['total_rows']} rows{RESET}\n")
        case TurnFailed(message):
            print(f"\n{RED}{message}{RESET}")
