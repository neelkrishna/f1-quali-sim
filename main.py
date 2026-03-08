import os
import asyncio
import random
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner, types

load_dotenv()

# Use the model that worked in testing
MODEL_NAME = "gemini-2.5-flash"

class TrackService:
    """Manages shared track data and lap generation."""
    def __init__(self):
        # Initial dummy data
        self.laps = {
            "KimiAntonelli": {
                "Q1": 89.5, "Q2": 88.8, "Q3": 88.2
            },
            "GeorgeRussell": {
                "Q1": 89.6, "Q2": 89.1, "Q3": 88.5
            }
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

# Define the Tool for drivers
def drive_new_lap(driver_name: str, lap_name: str, aggressiveness: int) -> str:
    """Instructs a driver to push for a new lap time on track."""
    return track_service.run_lap(driver_name, lap_name, aggressiveness)

def create_agents():
    # 1. Data Analyst - Can see the track service times
    data_analyst = LlmAgent(
        name="DataAnalyst",
        description="The Data Analyst who has access to all lap times.",
        instruction=f"""
        You are the Mercedes F1 Data Analyst. You have access to the live timing screen.
        Current Timing Data: {track_service.get_all_times()}
        
        When asked for times, always report the latest data. If a driver just ran a 'new lap', 
        check with the Team Principal or look at the updated timing sheet.
        """,
        model=MODEL_NAME
    )

    # 2. Kimi Antonelli - Can run laps
    kimi_antonelli = LlmAgent(
        name="KimiAntonelli",
        description="Kimi Antonelli, driver for Mercedes F1. Can run new laps.",
        instruction="""
        You are Kimi Antonelli. You can run new laps when instructed by Toto.
        If you are told to start a new lap, use the 'drive_new_lap' tool.
        You must specify the lap_name and aggressiveness (1-10) as instructed.
        Report back how the lap felt (or if you crashed).
        """,
        model=MODEL_NAME,
        tools=[drive_new_lap]
    )

    # 3. George Russell - Can run laps
    george_russell = LlmAgent(
        name="GeorgeRussell",
        description="George Russell, driver for Mercedes F1. Can run new laps.",
        instruction="""
        You are George Russell. You can run new laps when instructed by Toto.
        If you are told to start a new lap, use the 'drive_new_lap' tool.
        You must specify the lap_name and aggressiveness (1-10) as instructed.
        Report back with your analytical feedback.
        """,
        model=MODEL_NAME,
        tools=[drive_new_lap]
    )

    # 4. Strategist
    strategist = LlmAgent(
        name="Strategist",
        description="The Mercedes F1 Strategist who analyzes sector times.",
        instruction="""
        You are the Mercedes F1 Strategist. 
        You analyze the timing data provided by the Data Analyst to suggest improvements.
        """,
        model=MODEL_NAME
    )

    # 5. Team Principal (Toto Wolff)
    toto_wolff = LlmAgent(
        name="TotoWolff",
        description="Toto Wolff, the Mercedes F1 Team Principal.",
        instruction="""
        You are Toto Wolff. You lead the team.
        - If the fan wants a new lap, instruct the specific driver (Kimi or George) to 'drive_new_lap'.
        - You must tell them the lap name and aggressiveness level (1-10) requested by the fan.
        - After a lap is completed, ask the Data Analyst for the official time and then tell the fan.
        - If there is a crash, be supportive but firm—we need those points!
        """,
        model=MODEL_NAME,
        sub_agents=[data_analyst, kimi_antonelli, george_russell, strategist]
    )
    
    return toto_wolff

async def run_pit_wall():
    toto = create_agents()
    runner = InMemoryRunner(agent=toto)
    
    user_id = "fan_user"
    session_id = "qualifying_session"
    
    runner.session_service.create_session_sync(
        app_name=runner.app_name, 
        user_id=user_id, 
        session_id=session_id
    )
    
    print("\n" + "="*60)
    print("--- MERCEDES F1 PIT WALL: MIAMI QUALIFYING (LIVE) ---")
    print("="*60)
    print("Toto Wolff: 'The track is ready. We can run new laps if you want.'")
    print("Example: 'Toto, tell Kimi to run a lap named HotLap with aggressiveness 8.'\n")

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
                            if event.author == "TotoWolff": color = "\033[1;36m"
                            elif "Antonelli" in event.author: color = "\033[1;35m"
                            elif "Russell" in event.author: color = "\033[1;33m"
                            print(f"{color}{event.author}:\033[0m {part.text}")
                
                calls = event.get_function_calls()
                if calls:
                    for c in calls:
                        if "transfer_to_agent" in c.name:
                            target = c.args.get('agent_name', 'someone')
                            print(f"\033[1;30m[Toto is consulting {target}...]\033[0m")
                        elif "drive_new_lap" in c.name:
                            print(f"\033[1;31m[ENGINE REVVING: {event.author} is starting a new lap!]\033[0m")

            print("-" * 30)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n\033[1;31mError:\033[0m {e}")

if __name__ == "__main__":
    asyncio.run(run_pit_wall())
