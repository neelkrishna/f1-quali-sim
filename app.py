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
        # Store structured data for history tracking
        # driver -> list of {"name": str, "time_str": str, "seconds": float}
        self.history = {
            "LewisHamilton": [
                {"name": "Q1", "time_str": "1:29.500", "seconds": 89.5},
                {"name": "Q2", "time_str": "1:28.800", "seconds": 88.8},
                {"name": "Q3", "time_str": "1:28.200", "seconds": 88.2}
            ],
            "GeorgeRussell": [
                {"name": "Q1", "time_str": "1:29.600", "seconds": 89.6},
                {"name": "Q2", "time_str": "1:29.100", "seconds": 89.1},
                {"name": "Q3", "time_str": "1:28.500", "seconds": 88.5}
            ]
        }
        self.crashes = []

    def get_last_lap_seconds(self, driver_name):
        """Returns the duration of the most recent successful lap for a driver."""
        if driver_name in self.history and self.history[driver_name]:
            return self.history[driver_name][-1]["seconds"]
        return None

    def get_latest_lap_seconds(self, driver_name):
        """Alias for clarity in comparison."""
        return self.get_last_lap_seconds(driver_name)

    def run_lap(self, driver_name: str, lap_name: str, aggressiveness: int):
        crash_chance = aggressiveness * 0.05
        
        # Capture ghost times BEFORE adding the new lap
        last_lap_seconds = self.get_last_lap_seconds(driver_name)
        other_driver = "GeorgeRussell" if "Hamilton" in driver_name else "LewisHamilton"
        other_driver_latest = self.get_latest_lap_seconds(other_driver)

        if random.random() < crash_chance:
            result = {
                "status": "CRASH",
                "driver": driver_name,
                "lap_name": lap_name,
                "duration_seconds": 45.0,
                "last_lap_seconds": last_lap_seconds,
                "other_driver_latest": other_driver_latest,
                "time_str": "DNF",
                "msg": f"CRASH: {driver_name} lost control at aggressiveness {aggressiveness} and hit the wall in Sector 3."
            }
            self.crashes.append(f"{driver_name} CRASHED during lap '{lap_name}'!")
            return result

        base_time = 90.2
        improvement_per_level = 4.0 / 9.0
        target_time = base_time - (improvement_per_level * (aggressiveness - 1))
        final_time_seconds = target_time + (random.uniform(-0.3, 0.3))
        
        minutes = int(final_time_seconds // 60)
        seconds = final_time_seconds % 60
        time_str = f"{minutes}:{seconds:06.3f}"
        
        # Add to history
        if driver_name not in self.history:
            self.history[driver_name] = []
        self.history[driver_name].append({
            "name": lap_name,
            "time_str": time_str,
            "seconds": final_time_seconds
        })
        
        return {
            "status": "SUCCESS",
            "driver": driver_name,
            "lap_name": lap_name,
            "duration_seconds": final_time_seconds,
            "last_lap_seconds": last_lap_seconds,
            "other_driver_latest": other_driver_latest,
            "time_str": time_str,
            "msg": f"SUCCESS: {driver_name} completed '{lap_name}' with a time of {time_str} at aggressiveness {aggressiveness}."
        }

    def get_all_times(self):
        # Format for the agent's simplified view
        output = {}
        for driver, laps in self.history.items():
            output[driver] = {l["name"]: l["time_str"] for l in laps}
        return output

def create_pit_wall_system():
    service = TrackService()
    shared_context = {"last_lap": None}

    def drive_new_lap(driver_name: str, lap_name: str, aggressiveness: int) -> str:
        result_data = service.run_lap(driver_name, lap_name, aggressiveness)
        shared_context["last_lap"] = result_data
        return result_data["msg"]

    def get_live_timing_data() -> str:
        return str(service.get_all_times())

    data_analyst = LlmAgent(
        name="DataAnalyst",
        description="The Data Analyst.",
        instruction="You are the Mercedes F1 Data Analyst. Use 'get_live_timing_data' for latest lap times.",
        model=MODEL_NAME,
        tools=[get_live_timing_data]
    )

    lewis_hamilton = LlmAgent(
        name="LewisHamilton",
        description="Lewis Hamilton.",
        instruction="You are Lewis Hamilton. Use 'drive_new_lap' when told.",
        model=MODEL_NAME,
        tools=[drive_new_lap]
    )

    george_russell = LlmAgent(
        name="GeorgeRussell",
        description="George Russell.",
        instruction="You are George Russell. Use 'drive_new_lap' when told.",
        model=MODEL_NAME,
        tools=[drive_new_lap]
    )

    strategist = LlmAgent(
        name="Strategist",
        description="Strategist.",
        instruction="Analyze times. Consult DataAnalyst.",
        model=MODEL_NAME
    )

    toto_wolff = LlmAgent(
        name="TotoWolff",
        description="Toto Wolff.",
        instruction="""
        You are Toto Wolff.
        - To run a lap, you can either call 'drive_new_lap' yourself or delegate to Lewis or George.
        - Use 'get_live_timing_data' to check the results.
        """,
        model=MODEL_NAME,
        sub_agents=[data_analyst, lewis_hamilton, george_russell, strategist],
        tools=[drive_new_lap, get_live_timing_data]
    )
    
    runner = InMemoryRunner(agent=toto_wolff)
    runner.session_service.create_session_sync(
        app_name=runner.app_name, 
        user_id="fan_user", 
        session_id="qualifying_session"
    )
    return service, runner, shared_context

# --- Streamlit UI ---

st.set_page_config(page_title="Mercedes F1 Pit Wall", page_icon="🏎️", layout="wide")

if "system_initialized" not in st.session_state:
    service, runner, shared_ctx = create_pit_wall_system()
    st.session_state.track_service = service
    st.session_state.runner = runner
    st.session_state.shared_ctx = shared_ctx
    st.session_state.messages = [{"role": "TotoWolff", "content": "Hello! I am Toto. Welcome to our pit wall."}]
    st.session_state.system_initialized = True

def render_miami_track(active_dur, last_dur, other_dur, driver_name):
    active_color = "#A020F0" if "Hamilton" in driver_name else "#00D2BE"
    last_lap_color = "#FFFF00" # Yellow for Personal Last Lap
    other_driver_color = "#FF4B4B" # Red for Opponent/Other Driver Latest
    
    bg_color = "#1e1e1e"
    track_path = "M420,180 L460,180 Q480,180 480,160 L480,100 Q480,80 460,80 L350,80 Q330,80 320,100 L300,140 Q290,160 270,160 L150,160 Q130,160 120,140 L100,100 Q90,80 70,80 L40,80 Q20,80 20,100 L20,160 Q20,180 40,180 L100,180 Q120,180 130,160 L150,120 Q160,100 180,100 L280,100 Q300,100 310,120 L330,160 Q340,180 360,180 Z"

    # Ghost dot helper
    def get_ghost_svg(dur, color, label):
        if not dur: return ""
        return f"""
        <circle r="6" fill="{color}" opacity="0.6">
            <animateMotion dur="{dur}s" repeatCount="1" path="{track_path}" rotate="auto" fill="freeze"/>
        </circle>
        """

    html_code = f"""
    <div style="background: {bg_color}; padding: 20px; border-radius: 15px; border: 2px solid #333; text-align: center; color: white; font-family: sans-serif;">
        <div style="display: flex; justify-content: space-around; margin-bottom: 10px; font-size: 0.9em;">
            <span style="color: {active_color}">● LIVE LAP</span>
            {f'<span style="color: {last_lap_color}">● YOUR LAST LAP</span>' if last_dur else ''}
            {f'<span style="color: {other_driver_color}">● TEAMMATE LATEST</span>' if other_dur else ''}
        </div>
        <svg viewBox="0 0 500 250" xmlns="http://www.w3.org/2000/svg" style="width: 100%; max-width: 800px;">
            <path d="{track_path}" fill="none" stroke="#444" stroke-width="8" stroke-linejoin="round"/>
            <!-- Active Progress Trace -->
            <path d="{track_path}" fill="none" stroke="{active_color}" stroke-width="4" stroke-linecap="round" stroke-dasharray="1000" stroke-dashoffset="1000">
                <animate attributeName="stroke-dashoffset" from="1000" to="0" dur="{active_dur}s" fill="freeze" />
            </path>
            {get_ghost_svg(last_dur, last_lap_color, "Last")}
            {get_ghost_svg(other_dur, other_driver_color, "Other")}
            <!-- Live Car -->
            <circle r="9" fill="{active_color}">
                <animateMotion dur="{active_dur}s" repeatCount="1" path="{track_path}" rotate="auto" fill="freeze"/>
            </circle>
        </svg>
        <div style="margin-top: 15px; font-family: monospace; font-size: 1.5em; color: {active_color};">
            <span id="timer">0.000</span>s
        </div>
    </div>
    <script>
        let start = Date.now();
        let duration = {active_dur} * 1000;
        let timerDisplay = document.getElementById('timer');
        let interval = setInterval(() => {{
            let elapsed = Date.now() - start;
            if (elapsed >= duration) {{
                timerDisplay.innerText = ({active_dur}).toFixed(3);
                clearInterval(interval);
            }} else {{
                timerDisplay.innerText = (elapsed / 1000).toFixed(3);
            }}
        }}, 30);
    </script>
    """
    st.components.v1.html(html_code, height=480)

st.title("🏁 Mercedes F1 Pit Wall: Miami Qualifying")

with st.sidebar:
    st.header("📊 Live Timing Sheet")
    timing_data = st.session_state.track_service.get_all_times()
    for driver, laps in timing_data.items():
        with st.expander(f"{'Lewis Hamilton' if 'Hamilton' in driver else 'George Russell'}", expanded=True):
            for lap, time_val in laps.items():
                st.text(f"{lap}: {time_val}")

for msg in st.session_state.messages:
    role = msg["role"]
    if role == "system":
        st.markdown(f"*{msg['content']}*")
    else:
        avatar = "👨‍💼" if role == "TotoWolff" else "🟣" if "Hamilton" in role else "🔵" if "Russell" in role else "📊"
        with st.chat_message("assistant" if role != "user" else "user", avatar=avatar if role != "user" else "🧑‍💻"):
            st.markdown(f"**{role}:** {msg['content']}")

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
                            st.markdown(f"*[Toto is consulting {target}...]*")
                        elif "drive_new_lap" in c.name:
                            st.markdown(f"🔥 **[ENGINE REVVING: {event.author} is starting a new lap!]**")

                if st.session_state.shared_ctx["last_lap"]:
                    anim = st.session_state.shared_ctx["last_lap"]
                    st.session_state.shared_ctx["last_lap"] = None
                    
                    render_miami_track(
                        active_dur=anim["duration_seconds"],
                        last_dur=anim["last_lap_seconds"],
                        other_dur=anim["other_driver_latest"],
                        driver_name=anim["driver"]
                    )
                    time.sleep(anim["duration_seconds"])
                    
                    if anim["status"] == "CRASH":
                        st.error(f"⚠️ {anim['msg']}")
                    else:
                        st.success(f"🏁 {anim['msg']}")
                    st.session_state.messages.append({"role": "system", "content": f"Lap completed: {anim['time_str']}"})

                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            role = event.author
                            st.session_state.messages.append({"role": role, "content": part.text})
                            avatar = "👨‍💼" if role == "TotoWolff" else "🟣" if "Hamilton" in role else "🔵"
                            with st.chat_message("assistant", avatar=avatar):
                                st.markdown(f"**{role}:** {part.text}")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")
