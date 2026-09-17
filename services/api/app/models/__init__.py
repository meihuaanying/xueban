"""模型包：集中导出，保证 Alembic 能发现全部表。"""

from app.models.audit import AuditLog, SafetyEvent
from app.models.billing import (
    BillingCycle,
    Checkout,
    CheckoutStatus,
    Subscription,
    SubscriptionPlan,
)
from app.models.cards import KnowledgeCard
from app.models.chat import ChatMessage, ChatRole, ChatScene, ChatSession
from app.models.content import (
    KnowledgeEdge,
    KnowledgePoint,
    MistakeTag,
    Question,
    QuestionKnowledgePoint,
    QuestionMistakeTag,
    QuestionStatus,
    QuestionType,
)
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.models.exam import Exam, ExamAnswer, ExamKind, ExamStatus, GradingKind, GradingRecord
from app.models.governance import (
    AlertRecord,
    Experiment,
    ExperimentAssignment,
    InspectionReport,
    QuestionVersion,
)
from app.models.learning import (
    LearningProfile,
    MasteryRecord,
    MistakeBookEntry,
    MistakeState,
    Plan,
    PlanKind,
    PlanTask,
    ReviewCard,
    TaskStatus,
    TaskType,
)
from app.models.lesson import MicroLesson, MicroLessonStatus
from app.models.parent import ParentTask
from app.models.practice import PracticeRecord, PracticeSource
from app.models.report import AnalyticsEvent, ReportShare, WeeklyReport
from app.models.user import ParentChild, ParentControl, RefreshToken, SmsCode, User, UserRole

__all__ = [
    "AlertRecord",
    "AnalyticsEvent",
    "AuditLog",
    "BillingCycle",
    "ChatMessage",
    "ChatRole",
    "ChatScene",
    "ChatSession",
    "Checkout",
    "CheckoutStatus",
    "Document",
    "DocumentChunk",
    "DocumentStatus",
    "Exam",
    "ExamAnswer",
    "ExamKind",
    "ExamStatus",
    "Experiment",
    "ExperimentAssignment",
    "GradingKind",
    "GradingRecord",
    "InspectionReport",
    "KnowledgeCard",
    "KnowledgeEdge",
    "KnowledgePoint",
    "LearningProfile",
    "MasteryRecord",
    "MicroLesson",
    "MicroLessonStatus",
    "MistakeBookEntry",
    "MistakeState",
    "MistakeTag",
    "ParentChild",
    "ParentControl",
    "ParentTask",
    "Plan",
    "PlanKind",
    "PlanTask",
    "PracticeRecord",
    "PracticeSource",
    "Question",
    "QuestionKnowledgePoint",
    "QuestionMistakeTag",
    "QuestionStatus",
    "QuestionType",
    "QuestionVersion",
    "RefreshToken",
    "ReportShare",
    "ReviewCard",
    "SafetyEvent",
    "SmsCode",
    "Subscription",
    "SubscriptionPlan",
    "TaskStatus",
    "TaskType",
    "User",
    "UserRole",
    "WeeklyReport",
]
