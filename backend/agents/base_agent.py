"""
Base Agent for TravelQ - UPDATED to use existing infrastructure
All specialized agents inherit from this base class

Uses:
- logging_config.py for agent-specific logging
- settings.py for configuration
"""
from autogen import AssistantAgent
from typing import Dict, Any, List, Optional, Callable
from utils.logging_config import setup_agent_logging, log_agent_raw, log_agent_json
from config.settings import settings


class TravelQBaseAgent(AssistantAgent):
    """
    Base class for all TravelQ specialized agents
    Provides common functionality and structure
    
    Integrates with existing infrastructure:
    - Uses logging_config for agent-specific logs
    - Uses settings for configuration
    """
    
    # ✅ ADD THIS - Standard completion signal
    TASK_COMPLETED = "🟢 TASK_COMPLETED"

    def __init__(
        self,
        name: str,
        system_message: str,
        llm_config: Dict[str, Any],
        description: str = "",
        agent_type: Optional[str] = None,  # ✅ This is NOT - it's YOUR custom param
        **kwargs
    ):
        """
        Initialize the base TravelQ agent
        
        Args:
            name: Agent name
            system_message: System prompt for the agent
            llm_config: LLM configuration including model, functions, etc.
            description: Description of agent's role
        """
        self.description = description
        # Store YOUR custom parameter (don't pass it up)
        self.agent_type = agent_type or name.replace("Agent", "").lower()
        
        # Setup agent-specific logging using existing infrastructure
        # This creates logs/agents/{agent_name}.log
        self.logger = setup_agent_logging(
            agent_name=self.agent_type,
            fresh_start=True
        )
        
        # Pass only ConversableAgent-compatible parameters to parent
        super().__init__(
            name=name,
            system_message=system_message,
            llm_config=llm_config,
            description=description,  # ✅ This is OK - AutoGen knows it
            **kwargs  # ✅ Other AutoGen parameters
            # ❌ agent_type is NOT passed here!
        )
        
        log_agent_raw(f"✅ {name} initialized", agent_name=self.agent_type)


    
    def log_raw(self, message: str, level: str = "INFO"):
        """
        Log raw message to agent's log file
        
        Args:
            message: Message to log
            level: Logging level (INFO, WARNING, ERROR)
        """
        import logging
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR
        }
        log_agent_raw(
            message,
            agent_name=self.agent_type,
            level=level_map.get(level, logging.INFO)
        )
    
    def log_json(self, data: Dict[str, Any], label: Optional[str] = None):
        """
        Log JSON data to agent's log file
        
        Args:
            data: Dictionary to log as JSON
            label: Optional label for the JSON data
        """
        log_agent_json(
            data,
            agent_name=self.agent_type,
            label=label
        )
    
    # ✅ NEW CONVERSATION LOGGING METHODS
    
    def log_conversation_message(
        self, 
        message_type: str, 
        content: str, 
        sender: Optional[str] = None,
        truncate: int = 5000
    ):
        """
        Log conversation messages to agent's log file
        
        Args:
            message_type: Type of message (INCOMING, OUTGOING, SYSTEM)
            content: Message content
            sender: Who sent the message (for INCOMING messages)
            truncate: Truncate long messages to this length (0 = no truncation)
        """
        # Truncate if needed
        if truncate > 0 and len(content) > truncate:
            display_content = content[:truncate] + f"... (truncated, {len(content)} total chars)"
        else:
            display_content = content
        
        # Format based on message type
        if message_type == "INCOMING":
            prefix = "📨 INCOMING"
            if sender:
                prefix += f" from {sender}"
            log_msg = f"{prefix}:\n{display_content}\n"
        elif message_type == "OUTGOING":
            prefix = "📤 OUTGOING"
            if sender:
                prefix += f" to {sender}"
            log_msg = f"{prefix}:\n{display_content}\n"
        elif message_type == "SYSTEM":
            log_msg = f"⚙️ SYSTEM: {display_content}"
        else:
            log_msg = f"{message_type}: {display_content}"
        
        # Log with separator for readability
        separator = "-" * 80
        self.log_raw(separator)
        self.log_raw(log_msg)
        self.log_raw(separator)
    
    def log_full_conversation(self, messages: List[Dict[str, Any]]):
        """
        Log entire conversation history
        
        Args:
            messages: List of message dictionaries from AutoGen
        """
        self.log_raw("=" * 80)
        self.log_raw("📜 FULL CONVERSATION HISTORY")
        self.log_raw("=" * 80)
        
        for i, msg in enumerate(messages, 1):
            sender = msg.get('name', msg.get('role', 'Unknown'))
            content = msg.get('content', '')
            
            self.log_raw(f"\n[Message {i}] From: {sender}")
            self.log_raw(f"{content}")
            self.log_raw("-" * 40)
        
        self.log_raw("=" * 80)
        self.log_raw(f"End of conversation ({len(messages)} messages)")
        self.log_raw("=" * 80)
    
    def log_thinking(self, thought: str):
        """
        Log agent's internal thinking/reasoning
        
        Args:
            thought: What the agent is thinking/planning
        """
        self.log_raw(f"💭 THINKING: {thought}")
    
    def log_decision(self, decision: str, reasoning: str = ""):
        """
        Log agent's decision and reasoning
        
        Args:
            decision: The decision made
            reasoning: Why this decision was made
        """
        self.log_raw(f"✅ DECISION: {decision}")
        if reasoning:
            self.log_raw(f"   Reasoning: {reasoning}")
    
    # END OF NEW METHODS

    def extract_user_preferences(self, message: str) -> Dict[str, Any]:
        """
        Extract relevant user preferences from a message
        
        Args:
            message: Message string containing preferences
            
        Returns:
            Dictionary of extracted preferences
        """
        # This can be overridden by specialized agents
        # to extract domain-specific preferences
        return {}
    
    def format_response(self, data: Any, response_type: str = "standard") -> str:
        """
        Format agent response in a consistent way
        
        Args:
            data: Data to format
            response_type: Type of response (standard, error, summary)
            
        Returns:
            Formatted response string
        """
        if response_type == "error":
            return f"[{self.name} ERROR]: {data}"
        elif response_type == "summary":
            return f"[{self.name} SUMMARY]: {data}"
        else:
            return f"[{self.name}]: {data}"
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate inputs before processing
        
        Args:
            inputs: Dictionary of inputs to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Override in specialized agents
        return True, None
    
    def log_tool_call(self, tool_name: str, parameters: Dict[str, Any], result: Any):
        """
        Log tool/function calls for debugging
        
        Args:
            tool_name: Name of the tool called
            parameters: Parameters passed to the tool
            result: Result from the tool
        """
        self.log_json({
            "tool": tool_name,
            "parameters": parameters,
            "result_preview": str(result)[:200] + "..." if len(str(result)) > 200 else str(result)
        }, label=f"🔧 Tool Call: {tool_name}")
    
    def handle_error(self, error: Exception, context: str = "") -> str:
        """
        Handle errors gracefully
        
        Args:
            error: The exception that occurred
            context: Context about where the error occurred
            
        Returns:
            Formatted error message
        """
        error_msg = f"Error in {self.name}"
        if context:
            error_msg += f" ({context})"
        error_msg += f": {str(error)}"
        
        # Log to agent's log file
        self.log_raw(error_msg, level="ERROR")
        
        # Also log with traceback
        import traceback
        self.log_raw(traceback.format_exc(), level="ERROR")
        
        return self.format_response(error_msg, "error")

    @staticmethod
    def create_llm_config(
        model: Optional[str] = None,
        temperature: float = 0.7,
        functions: Optional[List[Dict[str, Any]]] = None,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create standard LLM configuration for agents
        
        Args:
            model: Model name (defaults to settings.llm_model)
            temperature: Temperature for generation
            functions: List of function definitions
            api_key: OpenAI API key (defaults to settings.openai_api_key)
            
        Returns:
            LLM config dictionary
        """
        config = {
            "model": model or settings.llm_model,
            "temperature": temperature,
            "seed": settings.autogen_cache_seed,
            "timeout": settings.autogen_timeout
        }
        
        if api_key:
            config["api_key"] = api_key
        elif settings.openai_api_key:
            config["api_key"] = settings.openai_api_key
        
        if functions:
            config["functions"] = functions
        
        return config

    def signal_completion(self, response: str) -> str:
        """
        Add standard completion signal to agent response
        
        Args:
            response: The agent's response text
            
        Returns:
            Response with completion signal appended
        """
        return f"{response}\n\n{self.TASK_COMPLETED}"

        
class ToolCallingMixin:
    """
    Mixin to add tool calling functionality to agents
    """
    
    def register_tool(
        self,
        tool_name: str,
        tool_function: Callable,
        tool_description: str,
        parameters_schema: Dict[str, Any]
    ):
        """
        Register a tool/function with the agent
        
        Args:
            tool_name: Name of the tool
            tool_function: The actual function to call
            tool_description: Description of what the tool does
            parameters_schema: JSON schema for the parameters
        """
        # AutoGen handles this through llm_config functions
        # This is a wrapper for clarity
        pass
    
    def call_tool(self, tool_name: str, **kwargs) -> Any:
        """
        Call a registered tool
        
        Args:
            tool_name: Name of the tool to call
            **kwargs: Parameters for the tool
            
        Returns:
            Tool result
        """
        # In AutoGen, tools are called automatically by the LLM
        # This is for direct programmatic calls if needed
        if hasattr(self, f"_{tool_name}"):
            return getattr(self, f"_{tool_name}")(**kwargs)
        else:
            raise ValueError(f"Tool {tool_name} not found")


class CachingMixin:
    """
    Mixin to add caching functionality to agents
    Uses settings for cache TTL
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache: Dict[str, Any] = {}
        self._cache_enabled = settings.cache_enabled
    
    def cache_result(self, key: str, value: Any):
        """Cache a result"""
        if self._cache_enabled:
            self._cache[key] = value
    
    def get_cached_result(self, key: str) -> Optional[Any]:
        """Get cached result"""
        if self._cache_enabled:
            return self._cache.get(key)
        return None
    
    def clear_cache(self):
        """Clear the cache"""
        self._cache.clear()


# Utility functions for all agents

def create_llm_config(
    model: Optional[str] = None,
    temperature: float = 0.7,
    functions: Optional[List[Dict[str, Any]]] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create standard LLM configuration for agents
    Uses settings.py for defaults
    
    Args:
        model: Model name (defaults to settings.llm_model)
        temperature: Temperature for generation
        functions: List of function definitions
        api_key: OpenAI API key (defaults to settings.openai_api_key)
        
    Returns:
        LLM config dictionary
    """
    config = {
        "model": model or settings.llm_model,
        "temperature": temperature,
        "seed": settings.autogen_cache_seed,
        "timeout": settings.autogen_timeout
    }
    
    # Use API key from settings if not provided
    if api_key:
        config["api_key"] = api_key
    elif settings.openai_api_key:
        config["api_key"] = settings.openai_api_key
    
    if functions:
        config["functions"] = functions
    
    return config


def create_function_schema(
    name: str,
    description: str,
    parameters: Dict[str, Any],
    required: List[str]
) -> Dict[str, Any]:
    """
    Create a function schema for tool calling
    
    Args:
        name: Function name
        description: What the function does
        parameters: Parameter definitions
        required: List of required parameter names
        
    Returns:
        Function schema dictionary
    """
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": parameters,
            "required": required
        }
    }


# Example usage
if __name__ == "__main__":
    from utils.logging_config import setup_logging
    
    # Setup main logging first
    setup_logging(log_file_name="travel_dashboard")
    
    # Example of creating a simple agent with the base class
    llm_config = create_llm_config()
    
    agent = TravelQBaseAgent(
        name="TestAgent",
        system_message="I am a test agent",
        llm_config=llm_config,
        description="Testing the base agent functionality"
    )
    
    # Test logging
    agent.log_raw("Test message from agent")
    agent.log_json({"test": "data", "status": "ok"}, label="Test Data")
    
    print(f"✅ Agent created: {agent.name}")
    print(f"📝 Description: {agent.description}")
    print(f"📂 Check logs at: logs/agents/testagent.log")