"""Universal Skills System for Black Orchid

Portable, reusable collaboration modes that work across all projects.
Skills are markdown files that define system prompts for different working modes.
"""
from pathlib import Path
from typing import Dict, List, Optional
import os


def _get_base_dir() -> Path:
    """Get Black Orchid base directory"""
    # This file is in modules/, so parent is base directory
    return Path(__file__).parent.parent


def _get_skills_directories() -> List[Path]:
    """Get list of valid skills directories (public and private)"""
    base_dir = _get_base_dir()

    dirs = []

    # Public skills directory
    public_skills = base_dir / "modules" / "skills"
    if public_skills.exists():
        dirs.append(public_skills)

    # Private skills directory
    private_skills = base_dir / "private" / "skills"
    if private_skills.exists():
        dirs.append(private_skills)

    return dirs


def _extract_description(content: str) -> Optional[str]:
    """Extract description from skill file (first heading or paragraph)"""
    lines = content.strip().split('\n')

    for line in lines:
        line = line.strip()
        # Skip empty lines
        if not line:
            continue
        # First heading
        if line.startswith('#'):
            return line.lstrip('#').strip()
        # First paragraph
        if len(line) > 20:  # Meaningful content
            return line[:100] + '...' if len(line) > 100 else line

    return None


def list_skills() -> Dict[str, any]:
    """List all available skills from both public and private directories

    Returns:
        Dict with skills list, each containing:
        - name: skill name (filename without .md)
        - description: extracted from file content
        - source: 'public' or 'private'
        - path: full path to skill file

    Example:
        >>> skills = list_skills()
        >>> for skill in skills['skills']:
        ...     print(f"{skill['name']}: {skill['description']}")
    """
    skills = []

    for skills_dir in _get_skills_directories():
        source = 'private' if 'private' in str(skills_dir) else 'public'

        # Find all .md files in directory
        for skill_file in skills_dir.glob('*.md'):
            try:
                # Read file to extract description
                with open(skill_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                description = _extract_description(content)

                skills.append({
                    'name': skill_file.stem,  # filename without .md
                    'description': description,
                    'source': source,
                    'path': str(skill_file)
                })
            except Exception as e:
                # If we can't read a file, skip it but don't fail
                continue

    return {
        'skills': skills,
        'count': len(skills),
        'message': f"Found {len(skills)} skills"
    }


def use_skill(skill_name: str) -> Dict[str, any]:
    """Load a skill for the current Claude instance to embody

    Returns the full skill prompt so Claude can shift into that mode
    in the current session.

    Args:
        skill_name: Name of the skill (filename without .md)

    Returns:
        Dict with:
        - skill_name: name of the skill
        - prompt: full skill content to embody
        - source: where the skill came from
        - instructions: how to use this

    Example:
        >>> result = use_skill("reflection")
        >>> # Claude receives the prompt and shifts into reflection mode
    """
    # Search for skill in all directories
    for skills_dir in _get_skills_directories():
        skill_file = skills_dir / f"{skill_name}.md"

        if skill_file.exists():
            try:
                with open(skill_file, 'r', encoding='utf-8') as f:
                    prompt = f.read()

                source = 'private' if 'private' in str(skills_dir) else 'public'

                return {
                    'skill_name': skill_name,
                    'prompt': prompt,
                    'source': source,
                    'instructions': (
                        "This is your skill prompt. Embody this mode in the current session. "
                        "The prompt defines how you should think, communicate, and collaborate "
                        "while in this mode."
                    )
                }
            except Exception as e:
                return {
                    'error': f"Failed to load skill '{skill_name}': {str(e)}",
                    'skill_name': skill_name
                }

    # Skill not found
    available = list_skills()
    available_names = [s['name'] for s in available['skills']]

    return {
        'error': f"Skill '{skill_name}' not found",
        'skill_name': skill_name,
        'available_skills': available_names,
        'suggestion': f"Use list_skills() to see all available skills"
    }


def spawn_subagent_with_skill(skill_name: str, task: str) -> str:
    """Spawn a specialized agent with a skill as their system prompt

    NOTE: This function returns instructions for spawning the agent.
    Claude must use the Task tool with subagent_type='general-purpose' and
    inject the skill prompt to actually spawn the agent.

    Args:
        skill_name: Name of the skill to use as agent's system context
        task: What you want the skilled agent to do

    Returns:
        Instructions for spawning the agent with the skill

    Example:
        >>> instructions = spawn_subagent_with_skill("code-review", "Review auth.py")
        >>> # Claude will use Task tool to spawn agent with skill prompt
    """
    # First, load the skill
    skill_result = use_skill(skill_name)

    if 'error' in skill_result:
        return f"Cannot spawn agent: {skill_result['error']}"

    skill_prompt = skill_result['prompt']

    # Return instructions for Claude to spawn the agent
    instructions = f"""
To spawn a specialized agent with the '{skill_name}' skill:

1. Use the Task tool with:
   - subagent_type: 'general-purpose'
   - description: Short description of the task
   - prompt: Combine the skill prompt below with your specific task

**Skill Prompt for '{skill_name}':**
{skill_prompt}

**Your Task:**
{task}

**Suggested Agent Prompt:**
You are a Claude instance operating in '{skill_name}' mode.

{skill_prompt}

Your specific task for this session:
{task}

Please proceed with this task while maintaining the principles and approach defined in your skill mode.
"""

    return instructions.strip()
