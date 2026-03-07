import os
import streamlit as st
import random
import asyncio
import time
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
            result = {
                "status": "CRASH",
                "driver": driver_name,
                "lap_name": lap_name,
                "duration_seconds": 45.0, # Crashes usually happen mid-lap
                "time_str": "DNF",
                "msg": f"CRASH: {driver_name} lost control at aggressiveness {aggressiveness} and hit the wall in Sector 3."
            }
            self.crashes.append(f"{driver_name} CRASHED during lap '{lap_name}'!")
            return result

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
        
        return {
            "status": "SUCCESS",
            "driver": driver_name,
            "lap_name": lap_name,
            "duration_seconds": final_time_seconds,
            "time_str": time_str,
            "msg": f"SUCCESS: {driver_name} completed '{lap_name}' with a time of {time_str} at aggressiveness {aggressiveness}."
        }

    def get_all_times(self):
        return self.laps

if "track_service" not in st.session_state:
    st.session_state.track_service = TrackService()

def drive_new_lap(driver_name: str, lap_name: str, aggressiveness: int) -> str:
    """Instructs a driver to push for a new lap time on track."""
    result_data = st.session_state.track_service.run_lap(driver_name, lap_name, aggressiveness)
    # Store result data in session state so the UI can trigger the animation
    st.session_state.pending_lap_animation = result_data
    return result_data["msg"]

def create_agents_and_runner():
    service = st.session_state.track_service

    data_analyst = LlmAgent(
        name="DataAnalyst",
        description="The Data Analyst who has access to all lap times.",
        instruction=lambda ctx: f"""
        You are the Mercedes F1 Data Analyst. You have access to the live timing screen.
        Current Timing Data: {service.get_all_times()}
        
        When asked for times, always report the latest data. 
        """,
        model=MODEL_NAME
    )

    lewis_hamilton = LlmAgent(
        name="LewisHamilton",
        description="Lewis Hamilton, driver for Mercedes F1. Can run new laps.",
        instruction="""
        You are Lewis Hamilton. Use 'drive_new_lap' when told to run a lap.
        Specify lap_name and aggressiveness (1-10).
        """,
        model=MODEL_NAME,
        tools=[drive_new_lap]
    )

    george_russell = LlmAgent(
        name="GeorgeRussell",
        description="George Russell, driver for Mercedes F1. Can run new laps.",
        instruction="""
        You are George Russell. Use 'drive_new_lap' when told to run a lap.
        Specify lap_name and aggressiveness (1-10).
        """,
        model=MODEL_NAME,
        tools=[drive_new_lap]
    )

    strategist = LlmAgent(
        name="Strategist",
        description="The Mercedes F1 Strategist.",
        instruction="Analyze times and suggest improvements.",
        model=MODEL_NAME
    )

    toto_wolff = LlmAgent(
        name="TotoWolff",
        description="Toto Wolff, the Mercedes F1 Team Principal.",
        instruction="""
        You are Toto Wolff. You lead the team.
        - To run a lap, instruct Lewis or George to 'drive_new_lap'.
        - You must tell them the lap name and aggressiveness (1-10).
        - IMPORTANT: When a lap is running, wait for it to finish.
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

def render_miami_track(duration, driver_name, status):
    """Renders a beautiful Miami track with a moving dot representing the driver."""
    
    color = "#A020F0" if "Hamilton" in driver_name else "#00D2BE"
    bg_color = "#1e1e1e"
    
    html_code = f"""
    <div id="track-container" style="background: {bg_color}; padding: 20px; border-radius: 15px; border: 2px solid #333; text-align: center;">
        <h3 style="color: white; font-family: sans-serif; margin-bottom: 10px;">{driver_name} on track...</h3>
        <svg viewBox="0 0 500 250" xmlns="http://www.w3.org/2000/svg" style="width: 100%; max-width: 800px;">
            <!-- Track Path -->
            <path 
                id="miami-track"
                d="M420,180 L460,180 Q480,180 480,160 L480,100 Q480,80 460,80 L350,80 Q330,80 320,100 L300,140 Q290,160 270,160 L150,160 Q130,160 120,140 L100,100 Q90,80 70,80 L40,80 Q20,80 20,100 L20,160 Q20,180 40,180 L100,180 Q120,180 130,160 L150,120 Q160,100 180,100 L280,100 Q300,100 310,120 L330,160 Q340,180 360,180 Z" 
                fill="none" 
                stroke="#444" 
                stroke-width="8" 
                stroke-linejoin="round"
            />
            <!-- Progress Track -->
            <path 
                id="progress-track"
                d="M420,180 L460,180 Q480,180 480,160 L480,100 Q480,80 460,80 L350,80 Q330,80 320,100 L300,140 Q290,160 270,160 L150,160 Q130,160 120,140 L100,100 Q90,80 70,80 L40,80 Q20,80 20,100 L20,160 Q20,180 40,180 L100,180 Q120,180 130,160 L150,120 Q160,100 180,100 L280,100 Q300,100 310,120 L330,160 Q340,180 360,180 Z" 
                fill="none" 
                stroke="{color}" 
                stroke-width="4" 
                stroke-linecap="round"
                stroke-dasharray="1000"
                stroke-dashoffset="1000"
            >
                <animate 
                    attributeName="stroke-dashoffset" 
                    from="1000" 
                    to="0" 
                    dur="{duration}s" 
                    fill="freeze" 
                />
            </path>
            <!-- Car Dot -->
            <circle r="8" fill="{color}" filter="drop-shadow(0 0 5px {color})">
                <animateMotion 
                    dur="{duration}s" 
                    repeatCount="1" 
                    path="M420,180 L460,180 Q480,180 480,160 L480,100 Q480,80 460,80 L350,80 Q330,80 320,100 L300,140 Q290,160 270,160 L150,160 Q130,160 120,140 L100,100 Q90,80 70,80 L40,80 Q20,80 20,100 L20,160 Q20,180 40,180 L100,180 Q120,180 130,160 L150,120 Q160,100 180,100 L280,100 Q300,100 310,120 L330,160 Q340,180 360,180 Z"
                    rotate="auto"
                    fill="freeze"
                />
            </circle>
        </svg>
        <div style="margin-top: 15px; color: #888; font-family: monospace; font-size: 1.2em;">
            LIVE TELEMETRY: <span id="timer">0.00</span>s
        </div>
    </div>
    <script>
        let start = Date.now();
        let duration = {duration} * 1000;
        let timerDisplay = document.getElementById('timer');
        
        let interval = setInterval(() => {{
            let elapsed = Date.now() - start;
            if (elapsed >= duration) {{
                timerDisplay.innerText = ({duration}).toFixed(2);
                clearInterval(interval);
            }} else {{
                timerDisplay.innerText = (elapsed / 1000).toFixed(2);
            }}
        }}, 50);
    </script>
    """
    st.components.v1.html(html_code, height=450)

# --- Streamlit UI ---

st.set_page_config(page_title="Mercedes F1 Pit Wall", page_icon="🏎️", layout="wide")
st.title("🏁 Mercedes F1 Pit Wall: Miami Qualifying")

if "runner" not in st.session_state:
    st.session_state.runner = create_agents_and_runner()
    st.session_state.messages = [
        {"role": "TotoWolff", "content": "Hello! I am Toto. Welcome to our pit wall. We are live in Miami."}
    ]

# Sidebar for Timing Sheet
with st.sidebar:
    st.header("📊 Live Timing Sheet")
    timing_data = st.session_state.track_service.get_all_times()
    for driver, laps in timing_data.items():
        with st.expander(f"{'Lewis Hamilton' if 'Hamilton' in driver else 'George Russell'}", expanded=True):
            for lap, time_val in laps.items():
                st.text(f"{lap}: {time_val}")

# Render chat history
for msg in st.session_state.messages:
    role = msg["role"]
    if role == "system":
        st.markdown(f"*{msg['content']}*")
    else:
        avatar = "👨‍💼" if role == "TotoWolff" else "Purple" if "Hamilton" in role else "Blue" if "Russell" in role else "📊"
        with st.chat_message("assistant" if role != "user" else "user", avatar=avatar if role != "user" else "🧑‍💻"):
            st.markdown(f"**{role}:** {msg['content']}")

# User Input
if prompt := st.chat_input("Message Toto Wolff..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(f"**user:** {prompt}")

    new_msg = types.Content(role="user", parts=[types.Part(text=prompt)])
    
    with st.spinner("Pit Wall is communicating..."):
        try:
            # We must process events one by one to catch the 'pending_lap_animation'
            events = st.session_state.runner.run(
                user_id="fan_user",
                session_id="qualifying_session",
                new_message=new_msg
            )
            
            for event in events:
                # Handle delegation visuals
                calls = event.get_function_calls()
                if calls:
                    for c in calls:
                        if "transfer_to_agent" in c.name:
                            target = c.args.get('agent_name', 'someone')
                            st.markdown(f"*[Toto is consulting {target}...]*")
                        elif "drive_new_lap" in c.name:
                            st.markdown(f"🔥 **[ENGINE REVVING: {event.author} is starting a new lap!]**")

                # Handle Text Responses
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            # Check if a lap was triggered by a tool call in a previous event of this run
                            if "pending_lap_animation" in st.session_state:
                                anim = st.session_state.pop("pending_lap_animation")
                                
                                # 1. Render the animation
                                render_miami_track(anim["duration_seconds"], anim["driver"], anim["status"])
                                
                                # 2. Real-time wait (Block Python)
                                time.sleep(anim["duration_seconds"])
                                
                                if anim["status"] == "CRASH":
                                    st.error(f"⚠️ {anim['msg']}")
                                else:
                                    st.success(f"🏁 {anim['msg']}")
                                
                                # Add to history
                                st.session_state.messages.append({"role": "system", "content": f"Lap completed: {anim['time_str']}"})

                            # Show agent response
                            role = event.author
                            st.session_state.messages.append({"role": role, "content": part.text})
                            avatar = "👨‍💼" if role == "TotoWolff" else "🟣" if "Hamilton" in role else "🔵"
                            with st.chat_message("assistant", avatar=avatar):
                                st.markdown(f"**{role}:** {part.text}")
            
            # Important: Streamlit needs a rerun to update the sidebar timing sheet after a lap
            st.rerun()
                                
        except Exception as e:
            st.error(f"Error: {e}")
