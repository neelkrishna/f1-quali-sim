import os
import asyncio
import random
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner, types

load_dotenv()

# Use the model that worked in testing
MODEL_NAME = "gemini-2.5-flash"

TEAMS = {
    "Mercedes": {
        "principal": "TotoWolff",
        "drivers": ["KimiAntonelli", "GeorgeRussell"]
    },
    "McLaren": {
        "principal": "AndreaStella",
        "drivers": ["LandoNorris", "OscarPiastri"]
    },
    "Ferrari": {
        "principal": "FredVasseur",
        "drivers": ["CharlesLeclerc", "LewisHamilton"]
    },
    "RedBull": {
        "principal": "ChristianHorner",
        "drivers": ["MaxVerstappen", "IsackHadjar"]
    }
}

class TrackService:
    """Manages shared track data and lap generation."""
    def __init__(self):
        self.laps = {}
        # Initial dummy data
        for team, data in TEAMS.items():
            for driver in data["drivers"]:
                self.laps[driver] = {
                    "Q1": f"1:{random.uniform(28.5, 29.5):06.3f}",
                    "Q2": f"1:{random.uniform(28.0, 29.0):06.3f}",
                    "Q3": f"1:{random.uniform(27.5, 28.5):06.3f}"
                }
        self.crashes = []

    def run_lap(self, driver_name: str, lap_name: str, aggressiveness: int):
        """Generates a new lap time or a crash based on aggressiveness."""
        # 5% crash chance per aggressiveness level (1=5%, 10=50%)
        crash_chance = aggressiveness * 0.05
        if random.random() < crash_chance:
            self.crashes.append(f"{driver_name} CRASHED during lap '{lap_name}'!")
            return f"CRASH: {driver_name} lost control at aggressiveness {aggressiveness} and hit the wall in Sector 3."

        # Performance Tradeoff:
        # Aggressiveness 10 is ~1:26.2 (Miami Record)
        # Aggressiveness 1 is ~1:30.2 (4 seconds off pace)
        # Formula: Base (1:30.2) - (improvement_per_level * (level - 1))
        # improvement_per_level = 4.0 / 9 = ~0.444s
        
        base_time = 90.2 # 1:30.2 in seconds
        improvement_per_level = 4.0 / 9.0
        
        # Calculate target time for this level
        target_time = base_time - (improvement_per_level * (aggressiveness - 1))
        
        # Add small random variance (+/- 0.3s) for realism
        final_time_seconds = target_time + (random.uniform(-0.3, 0.3))
        
        # Format back to MM:SS.ms
        minutes = int(final_time_seconds // 60)
        seconds = final_time_seconds % 60
        time_str = f"{minutes}:{seconds:06.3f}"
        
        if driver_name not in self.laps:
            self.laps[driver_name] = {}
        
        self.laps[driver_name][lap_name] = time_str
        return f"SUCCESS: {driver_name} completed '{lap_name}' with a time of {time_str} at aggressiveness {aggressiveness}."

    def get_all_times(self):
        return self.laps

track_service = TrackService()

def drive_new_lap(driver_name: str, lap_name: str, aggressiveness: int) -> str:
    """Instructs a driver to push for a new lap time on track."""
    return track_service.run_lap(driver_name, lap_name, aggressiveness)

def get_live_timing_data() -> str:
    """Returns the latest lap times for all drivers."""
    return str(track_service.get_all_times())

def create_team_agents(team_name: str, principal_name: str, drivers: list[str]):
    data_analyst = LlmAgent(
        name=f"{team_name}DataAnalyst",
        description=f"The {team_name} Data Analyst who has access to all lap times.",
        instruction=f"""
        You are the {team_name} Data Analyst. You have access to the live timing screen.
        When asked for times, always report the latest data using the 'get_live_timing_data' tool. 
        If a driver just ran a 'new lap', check with the Team Principal or look at the updated timing sheet.
        """,
        model=MODEL_NAME,
        tools=[get_live_timing_data]
    )

    driver_agents = []
    for driver_name in drivers:
        driver_agents.append(LlmAgent(
            name=driver_name,
            description=f"{driver_name}, driver for {team_name}. Can run new laps.",
            instruction=f"""
            You are {driver_name}. You can run new laps when instructed by {principal_name}.
            If you are told to start a new lap, use the 'drive_new_lap' tool.
            You must specify your own name as driver_name, the lap_name and aggressiveness (1-10) as instructed.
            Report back how the lap felt (or if you crashed).
            """,
            model=MODEL_NAME,
            tools=[drive_new_lap]
        ))

    strategist = LlmAgent(
        name=f"{team_name}Strategist",
        description=f"The {team_name} Strategist who analyzes sector times.",
        instruction=f"""
        You are the {team_name} Strategist. 
        You analyze the timing data provided by the Data Analyst to suggest improvements.
        """,
        model=MODEL_NAME
    )

    principal = LlmAgent(
        name=principal_name,
        description=f"{principal_name}, the {team_name} Team Principal.",
        instruction=f"""
        You are {principal_name}. You lead the {team_name} team.
        - You can instruct your drivers ({', '.join(drivers)}) to run laps by transferring to them.
        - You must tell them the lap name and aggressiveness level (1-10).
        - After a lap is completed, ask the Data Analyst for the official time.
        - If there is a crash, be supportive but firm—we need those points!
        """,
        model=MODEL_NAME,
        sub_agents=[data_analyst, strategist] + driver_agents
    )
    
    return principal

def create_coordinator():
    team_principals = []
    for team_name, data in TEAMS.items():
        team_principals.append(create_team_agents(team_name, data["principal"], data["drivers"]))

    coordinator = LlmAgent(
        name="Coordinator",
        description="The F1 Coordinator Super Agent who receives user requests and routes them to the correct Team Principal.",
        instruction="""
        You are the F1 Coordinator Super Agent. You sit above all teams.
        Your job is to read the user's instructions and route the conversation to the correct Team Principal.
        You have access to the Team Principals of Mercedes (TotoWolff), McLaren (AndreaStella), Ferrari (FredVasseur), and Red Bull (ChristianHorner).
        If the user asks to talk to a specific principal, transfer to them. If they ask to give instructions to a driver, figure out which team they are on and transfer to that Team Principal.
        Once the Team Principal gives their verdict, report back to the user.
        """,
        model=MODEL_NAME,
        sub_agents=team_principals
    )
    return coordinator

async def run_pit_wall():
    coordinator = create_coordinator()
    runner = InMemoryRunner(agent=coordinator)
    
    user_id = "fan_user"
    session_id = "qualifying_session"
    
    runner.session_service.create_session_sync(
        app_name=runner.app_name, 
        user_id=user_id, 
        session_id=session_id
    )
    
    print("\n" + "="*60)
    print("--- 2026 F1 MULTI-TEAM PIT WALL: MIAMI QUALIFYING (LIVE) ---")
    print("="*60)
    print("Coordinator: 'The track is ready. We have Mercedes, McLaren, Ferrari, and Red Bull.'")
    print("Example: 'Connect me to Andrea Stella, I want Lando Norris to run a HotLap with aggressiveness 8.'\n")

    while True:
        try:
            user_input = input("\033[1;32mYou:\033[0m ")
            if user_input.lower() in ["exit", "quit", "bye"]:
                break
            
            new_msg = types.Content(role="user", parts=[types.Part(text=user_input)])
            print("\n\033[1;30m[Pit Wall Activity...]\033[0m")
            
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=new_msg
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            color = "\033[1;34m"
                            is_principal = any(event.author == data["principal"] for data in TEAMS.values())
                            is_coordinator = event.author == "Coordinator"
                            if is_principal: color = "\033[1;36m"
                            elif is_coordinator: color = "\033[1;37m"
                            elif "Analyst" in event.author: color = "\033[1;32m"
                            elif "Strategist" in event.author: color = "\033[1;32m"
                            else: color = "\033[1;33m" # Driver
                            print(f"{color}{event.author}:\033[0m {part.text}")
                
                calls = event.get_function_calls()
                if calls:
                    for c in calls:
                        if "transfer_to_agent" in c.name:
                            target = c.args.get('agent_name', 'someone')
                            print(f"\033[1;30m[{event.author} is transferring to {target}...]\033[0m")
                        elif "drive_new_lap" in c.name:
                            print(f"\033[1;31m[ENGINE REVVING: {event.author} is starting a new lap!]\033[0m")
                        elif "get_live_timing_data" in c.name:
                            print(f"\033[1;30m[{event.author} is checking the live timing sheet...]\033[0m")

            print("-" * 30)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n\033[1;31mError:\033[0m {e}")

if __name__ == "__main__":
    asyncio.run(run_pit_wall())
