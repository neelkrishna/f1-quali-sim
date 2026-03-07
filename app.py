import os
import streamlit as st
import random
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner, types

load_dotenv()

MODEL_NAME = "gemini-2.5-flash"

class TrackService:
    """Manages shared track data and lap generation."""
    def __init__(self):
        self.laps = {
            "LewisHamilton": {"Q1": "1:29.500", "Q2": "1:28.800", "Q3": "1:28.200"},
            "GeorgeRussell": {"Q1": "1:29.600", "Q2": "1:29.100", "Q3": "1:28.500"}
        }
        self.crashes = []

    def run_lap(self, driver_name: str, lap_name: str, aggressiveness: int):
        crash_chance = aggressiveness * 0.05
        if random.random() < crash_chance:
            self.crashes.append(f"{driver_name} CRASHED during lap '{lap_name}'!")
            return f"CRASH: {driver_name} lost control at aggressiveness {aggressiveness} and hit the wall in Sector 3."

        base_time = 90.2 # 1:30.2
        improvement_per_level = 4.0 / 9.0
        target_time = base_time - (improvement_per_level * (aggressiveness - 1))
        final_time_seconds = target_time + (random.uniform(-0.3, 0.3))
        
        minutes = int(final_time_seconds // 60)
        seconds = final_time_seconds % 60
        time_str = f"{minutes}:{seconds:06.3f}"
        
        if driver_name not in self.laps:
            self.laps[driver_name] = {}
        
        self.laps[driver_name][lap_name] = time_str
        return f"SUCCESS: {driver_name} completed '{lap_name}' with a time of {time_str} at aggressiveness {aggressiveness}."

    def get_all_times(self):
        return self.laps

# We need to initialize the service in session state so it persists across streamlit reruns
if "track_service" not in st.session_state:
    st.session_state.track_service = TrackService()

def create_agents_and_runner():
    # Capture the service instance in the closure to avoid st.session_state access issues later
    service = st.session_state.track_service

    # Define the tool within this scope so it also captures 'service'
    def drive_new_lap(driver_name: str, lap_name: str, aggressiveness: int) -> str:
        """Instructs a driver to push for a new lap time on track."""
        return service.run_lap(driver_name, lap_name, aggressiveness)

    data_analyst = LlmAgent(
        name="DataAnalyst",
        description="The Data Analyst who has access to all lap times.",
        instruction=lambda ctx: f"""
        You are the Mercedes F1 Data Analyst. You have access to the live timing screen.
        Current Timing Data: {service.get_all_times()}
        
        When asked for times, always report the latest data. If a driver just ran a 'new lap', 
        check with the Team Principal or look at the updated timing sheet.
        """,
        model=MODEL_NAME
    )

    lewis_hamilton = LlmAgent(
        name="LewisHamilton",
        description="Lewis Hamilton, driver for Mercedes F1. Can run new laps.",
        instruction="""
        You are Lewis Hamilton. You can run new laps when instructed by Toto.
        If you are told to start a new lap, use the 'drive_new_lap' tool.
        You must specify the lap_name and aggressiveness (1-10) as instructed.
        Report back how the lap felt (or if you crashed).
        """,
        model=MODEL_NAME,
        tools=[drive_new_lap]
    )

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

    strategist = LlmAgent(
        name="Strategist",
        description="The Mercedes F1 Strategist who analyzes sector times.",
        instruction="""
        You are the Mercedes F1 Strategist. 
        You analyze the timing data provided by the Data Analyst to suggest improvements.
        """,
        model=MODEL_NAME
    )

    toto_wolff = LlmAgent(
        name="TotoWolff",
        description="Toto Wolff, the Mercedes F1 Team Principal.",
        instruction="""
        You are Toto Wolff. You lead the team.
        - If the fan wants a new lap, instruct the specific driver (Lewis or George) to 'drive_new_lap'.
        - You must tell them the lap name and aggressiveness level (1-10) requested by the fan.
        - After a lap is completed, ask the Data Analyst for the official time and then tell the fan.
        - If there is a crash, be supportive but firm—we need those points!
        """,
        model=MODEL_NAME,
        sub_agents=[data_analyst, lewis_hamilton, george_russell, strategist]
    )
    
    runner = InMemoryRunner(agent=toto_wolff)
    runner.session_service.create_session_sync(
        app_name=runner.app_name, 
        user_id="fan_user", 
        session_id="qualifying_session"
    )
    return runner

# --- Streamlit UI ---

st.set_page_config(page_title="Mercedes F1 Pit Wall", page_icon="🏎️", layout="wide")
st.title("🏁 Mercedes F1 Pit Wall: Miami Qualifying")
st.markdown("Speak with Toto Wolff and the team. You can ask drivers to run new laps!")

if "runner" not in st.session_state:
    st.session_state.runner = create_agents_and_runner()
    st.session_state.messages = [
        {"role": "TotoWolff", "content": "Hello! I am Toto. Welcome to our pit wall. The track is ready. We can run new laps if you want."}
    ]

# Render chat history
for msg in st.session_state.messages:
    role = msg["role"]
    avatar = "🏎️"
    if role == "TotoWolff": avatar = "👨‍💼"
    elif role == "user": avatar = "🧑‍💻"
    elif "Hamilton" in role: avatar = "🟣"
    elif "Russell" in role: avatar = "🔵"
    elif "DataAnalyst" in role: avatar = "📊"
    elif "Strategist" in role: avatar = "📈"
    elif role == "system": avatar = "🔄"

    if role == "system":
        st.markdown(f"*{msg['content']}*")
    else:
        with st.chat_message(role if role in ["user", "assistant"] else "assistant", avatar=avatar):
            st.markdown(f"**{role}:** {msg['content']}")

# User Input
if prompt := st.chat_input("Message Toto Wolff..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(f"**user:** {prompt}")

    new_msg = types.Content(role="user", parts=[types.Part(text=prompt)])
    
    with st.spinner("Pit Wall is communicating..."):
        try:
            events = st.session_state.runner.run(
                user_id="fan_user",
                session_id="qualifying_session",
                new_message=new_msg
            )
            
            for event in events:
                calls = event.get_function_calls()
                if calls:
                    for c in calls:
                        if "transfer_to_agent" in c.name:
                            target = c.args.get('agent_name', 'someone')
                            sys_msg = f"[Toto is consulting {target}...]"
                            st.session_state.messages.append({"role": "system", "content": sys_msg})
                            st.markdown(f"*{sys_msg}*")
                        elif "drive_new_lap" in c.name:
                            sys_msg = f"🔥 [ENGINE REVVING: {event.author} is starting a new lap!]"
                            st.session_state.messages.append({"role": "system", "content": sys_msg})
                            st.markdown(f"*{sys_msg}*")

                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            role = event.author
                            avatar = "🏎️"
                            if role == "TotoWolff": avatar = "👨‍💼"
                            elif "Hamilton" in role: avatar = "🟣"
                            elif "Russell" in role: avatar = "🔵"
                            elif "DataAnalyst" in role: avatar = "📊"
                            elif "Strategist" in role: avatar = "📈"

                            st.session_state.messages.append({"role": role, "content": part.text})
                            with st.chat_message("assistant", avatar=avatar):
                                st.markdown(f"**{role}:** {part.text}")
                                
        except Exception as e:
            st.error(f"Error processing message: {e}")
