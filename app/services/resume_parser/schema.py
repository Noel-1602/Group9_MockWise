"""Pydantic schemas representing structured resume data."""

import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ExperienceItem(BaseModel):
    """Schema representing an employment or work experience entry."""
    model_config = ConfigDict(extra="ignore")

    role: str = Field(description="Job title or role")
    company: str = Field(description="Company or organization name")
    location: Optional[str] = Field(default=None, description="Location of the job")
    start_date: Optional[str] = Field(default=None, description="Start date (e.g., 'Jan 2021')")
    end_date: Optional[str] = Field(default=None, description="End date (e.g., 'Present' or 'Dec 2023')")
    description: Optional[str] = Field(default=None, description="Summary of responsibilities")
    highlights: List[str] = Field(default_factory=list, description="Key achievements or bullet points")


class EducationItem(BaseModel):
    """Schema representing an academic degree or educational credential."""
    model_config = ConfigDict(extra="ignore")

    degree: str = Field(description="Degree name (e.g., 'B.S. in Computer Science')")
    institution: str = Field(description="College or university name")
    graduation_year: Optional[str] = Field(default=None, description="Graduation year or date range")
    field_of_study: Optional[str] = Field(default=None, description="Major or area of study")
    details: Optional[str] = Field(default=None, description="GPA, honors, or relevant coursework")


class ProjectItem(BaseModel):
    """Schema representing a personal or professional project."""
    model_config = ConfigDict(extra="ignore")

    title: str = Field(description="Project name or title")
    description: Optional[str] = Field(default=None, description="Overview of the project")
    technologies: List[str] = Field(default_factory=list, description="Technologies/tools used")
    link: Optional[str] = Field(default=None, description="URL or repository link")


class StructuredResume(BaseModel):
    """Normalized structured resume representation."""
    model_config = ConfigDict(extra="ignore")

    candidate_name: Optional[str] = Field(default=None, description="Candidate's full name")
    email: Optional[str] = Field(default=None, description="Candidate email address")
    phone: Optional[str] = Field(default=None, description="Candidate contact phone number")
    summary: Optional[str] = Field(default=None, description="Professional summary or objective")
    skills: List[str] = Field(default_factory=list, description="List of technical/soft skills")
    experience: List[ExperienceItem] = Field(default_factory=list, description="List of work experience entries")
    education: List[EducationItem] = Field(default_factory=list, description="List of education entries")
    projects: List[ProjectItem] = Field(default_factory=list, description="List of projects")
    raw_text: Optional[str] = Field(default=None, description="Raw or cleaned text of the resume")

    def to_db_json(self) -> Dict[str, Any]:
        """Convert structured fields into JSON-encoded strings matching Resume model columns."""
        return {
            "skills_json": json.dumps(self.skills),
            "projects_json": json.dumps([p.model_dump() for p in self.projects]),
            "experience_json": json.dumps([e.model_dump() for e in self.experience]),
            "education_json": json.dumps([ed.model_dump() for ed in self.education]),
            "raw_text": self.raw_text or "",
        }


# ---------------------------------------------------------------------------
# Flat DB-column-aligned models
#
# These map one-to-one onto the four JSON text columns on the Resume table:
#   skills_json      → List[str]                   (ParsedResume.skills)
#   projects_json    → List[{title, description}]  (ParsedResume.projects)
#   experience_json  → List[str]                   (ParsedResume.experience)
#   education_json   → List[str]                   (ParsedResume.education)
#
# They are intentionally simpler than the rich models above so that code that
# only needs to read from / write to the database can import a minimal shape
# without depending on the full StructuredResume graph.
# ---------------------------------------------------------------------------


class ResumeProject(BaseModel):
    """A single project entry as stored in projects_json.

    Deliberately flat: just a title and a free-text description so the value
    serialises cleanly as ``{"title": "...", "description": "..."}``.
    """
    model_config = ConfigDict(extra="ignore")

    title: str = Field(description="Project name or title")
    description: str = Field(description="Brief overview of the project")


class ParsedResume(BaseModel):
    """Flat structured resume aligned with the four JSON columns on the Resume table.

    Each field serialises directly to the corresponding DB column:

    * ``skills``     → ``skills_json``      (``json.dumps(skills)``)
    * ``projects``   → ``projects_json``    (``json.dumps([p.model_dump() for p in projects])``)
    * ``experience`` → ``experience_json``  (``json.dumps(experience)``)
    * ``education``  → ``education_json``   (``json.dumps(education)``)
    """
    model_config = ConfigDict(extra="ignore")

    skills: List[str] = Field(
        default_factory=list,
        description="Flat list of skill strings (e.g. ['Python', 'FastAPI'])",
    )
    projects: List[ResumeProject] = Field(
        default_factory=list,
        description="List of project objects, each with title and description",
    )
    experience: List[str] = Field(
        default_factory=list,
        description="Flat list of experience strings (e.g. 'Software Engineer at Acme, 2022–2024')",
    )
    education: List[str] = Field(
        default_factory=list,
        description="Flat list of education strings (e.g. 'B.Sc. CS, University of Technology, 2022')",
    )

    def to_db_columns(self) -> Dict[str, str]:
        """Return a dict of ``{column_name: json_string}`` ready to write to the Resume table."""
        return {
            "skills_json": json.dumps(self.skills),
            "projects_json": json.dumps([p.model_dump() for p in self.projects]),
            "experience_json": json.dumps(self.experience),
            "education_json": json.dumps(self.education),
        }

