from __future__ import annotations

from typing import TypedDict

from cvm_platform.domain.types import ResumeProjectionPayload


class MockCandidatePayload(TypedDict):
    external_identity_id: str
    name: str
    title: str
    company: str
    location: str
    summary: str
    email: str
    phone: str
    resumeProjection: ResumeProjectionPayload


MOCK_CANDIDATES: list[MockCandidatePayload] = [
    {
        "external_identity_id": "cts_001",
        "name": "张晨",
        "title": "Senior Backend Engineer",
        "company": "ByteDance",
        "location": "Shanghai",
        "summary": "Python, FastAPI, PostgreSQL, search systems",
        "email": "zhangchen@example.com",
        "phone": "13812345678",
        "resumeProjection": {
            "workYear": 7,
            "currentLocation": "Shanghai",
            "expectedLocation": "Shanghai",
            "jobState": "OpenToWork",
            "expectedSalary": "45k-60k",
            "age": 31,
            "education": [
                {
                    "school": "Fudan University",
                    "degree": "Master",
                    "major": "Computer Science",
                    "startTime": "2013-09",
                    "endTime": "2016-06",
                }
            ],
            "workExperience": [
                {
                    "company": "ByteDance",
                    "title": "Senior Backend Engineer",
                    "duration": "2021-01 ~ now",
                    "startTime": "2021-01",
                    "endTime": None,
                    "summary": "Built candidate ranking and workflow orchestration systems.",
                }
            ],
            "workSummaries": [
                "Built candidate ranking and workflow orchestration systems.",
                "Owned Python and FastAPI search APIs.",
            ],
            "projectNames": ["candidate ranking", "workflow systems"],
        },
    },
    {
        "external_identity_id": "cts_002",
        "name": "王蕾",
        "title": "AI Product Engineer",
        "company": "OpenSource Labs",
        "location": "Beijing",
        "summary": "Angular, agents, evals, product ops",
        "email": "wanglei@example.com",
        "phone": "13999990001",
        "resumeProjection": {
            "workYear": 5,
            "currentLocation": "Beijing",
            "expectedLocation": "Beijing",
            "jobState": "OpenToWork",
            "expectedSalary": "35k-50k",
            "age": 29,
            "education": [
                {
                    "school": "Tsinghua University",
                    "degree": "Bachelor",
                    "major": "Software Engineering",
                    "startTime": "2014-09",
                    "endTime": "2018-06",
                }
            ],
            "workExperience": [
                {
                    "company": "OpenSource Labs",
                    "title": "AI Product Engineer",
                    "duration": "2022-03 ~ now",
                    "startTime": "2022-03",
                    "endTime": None,
                    "summary": "Shipped agent console and ops dashboard for eval-heavy products.",
                }
            ],
            "workSummaries": [
                "Shipped agent console and ops dashboard for eval-heavy products.",
                "Used Angular and TypeScript across recruiting workflows.",
            ],
            "projectNames": ["agent console", "ops dashboard"],
        },
    },
    {
        "external_identity_id": "cts_003",
        "name": "李骁",
        "title": "Platform Engineer",
        "company": "Tencent",
        "location": "Shenzhen",
        "summary": "Temporal, Python, reliability, tooling",
        "email": "lixiao@example.com",
        "phone": "13711112222",
        "resumeProjection": {
            "workYear": 8,
            "currentLocation": "Shenzhen",
            "expectedLocation": "Shenzhen",
            "jobState": "Passive",
            "expectedSalary": "50k-70k",
            "age": 33,
            "education": [
                {
                    "school": "Zhejiang University",
                    "degree": "Master",
                    "major": "Computer Engineering",
                    "startTime": "2011-09",
                    "endTime": "2014-06",
                }
            ],
            "workExperience": [
                {
                    "company": "Tencent",
                    "title": "Platform Engineer",
                    "duration": "2020-07 ~ now",
                    "startTime": "2020-07",
                    "endTime": None,
                    "summary": "Led workflow migration and ops automation for reliability teams.",
                }
            ],
            "workSummaries": [
                "Led workflow migration and ops automation for reliability teams.",
            ],
            "projectNames": ["workflow migration", "ops automation"],
        },
    },
    {
        "external_identity_id": "cts_004",
        "name": "陈越",
        "title": "Recruiting Data Analyst",
        "company": "Mercury Search",
        "location": "Shanghai",
        "summary": "Data quality, CRM, candidate operations",
        "email": "chenyue@example.com",
        "phone": "13688887777",
        "resumeProjection": {
            "workYear": 4,
            "currentLocation": "Shanghai",
            "expectedLocation": "Shanghai",
            "jobState": "OpenToWork",
            "expectedSalary": "18k-25k",
            "age": 27,
            "education": [
                {
                    "school": "SJTU",
                    "degree": "Bachelor",
                    "major": "Statistics",
                    "startTime": "2015-09",
                    "endTime": "2019-06",
                }
            ],
            "workExperience": [
                {
                    "company": "Mercury Search",
                    "title": "Recruiting Data Analyst",
                    "duration": "2022-01 ~ now",
                    "startTime": "2022-01",
                    "endTime": None,
                    "summary": "Owned candidate pipeline data quality and operations analytics.",
                }
            ],
            "workSummaries": [
                "Owned candidate pipeline data quality and operations analytics.",
            ],
            "projectNames": ["candidate pipeline insights"],
        },
    },
    {
        "external_identity_id": "cts_005",
        "name": "赵敏",
        "title": "LLM Application Engineer",
        "company": "Ant Group",
        "location": "Hangzhou",
        "summary": "Python, agents, retrieval, evaluation workflows",
        "email": "zhaomin@example.com",
        "phone": "13566668888",
        "resumeProjection": {
            "workYear": 6,
            "currentLocation": "Hangzhou",
            "expectedLocation": "Hangzhou",
            "jobState": "OpenToWork",
            "expectedSalary": "40k-55k",
            "age": 30,
            "education": [
                {
                    "school": "Zhejiang University",
                    "degree": "Master",
                    "major": "Software Engineering",
                    "startTime": "2012-09",
                    "endTime": "2015-06",
                }
            ],
            "workExperience": [
                {
                    "company": "Ant Group",
                    "title": "LLM Application Engineer",
                    "duration": "2021-04 ~ now",
                    "startTime": "2021-04",
                    "endTime": None,
                    "summary": "Built agent retrieval flows with Python services and automated eval gates.",
                }
            ],
            "workSummaries": [
                "Built agent retrieval flows with Python services and automated eval gates.",
                "Owned search ranking experiments and recruiter tooling.",
            ],
            "projectNames": ["agent retrieval", "eval gates"],
        },
    },
    {
        "external_identity_id": "cts_006",
        "name": "周宁",
        "title": "Applied AI Engineer",
        "company": "MiniMax",
        "location": "Shanghai",
        "summary": "ReAct, prompt engineering, Python, workflow orchestration",
        "email": "zhouning@example.com",
        "phone": "13500001111",
        "resumeProjection": {
            "workYear": 5,
            "currentLocation": "Shanghai",
            "expectedLocation": "Shanghai",
            "jobState": "Passive",
            "expectedSalary": "38k-52k",
            "age": 29,
            "education": [
                {
                    "school": "Tongji University",
                    "degree": "Bachelor",
                    "major": "Automation",
                    "startTime": "2013-09",
                    "endTime": "2017-06",
                }
            ],
            "workExperience": [
                {
                    "company": "MiniMax",
                    "title": "Applied AI Engineer",
                    "duration": "2022-06 ~ now",
                    "startTime": "2022-06",
                    "endTime": None,
                    "summary": "Implemented ReAct loops, prompt tuning, and workflow orchestration for agent products.",
                }
            ],
            "workSummaries": [
                "Implemented ReAct loops, prompt tuning, and workflow orchestration for agent products.",
                "Worked on shortlist reasoning and user-facing agent summaries.",
            ],
            "projectNames": ["react orchestration", "agent shortlist"],
        },
    },
]
