"""测试数据工厂（factory-boy）。"""

from __future__ import annotations

import factory

from app.models import Question, QuestionStatus, QuestionType, User, UserRole
from app.services.security import hash_password
from tests.conftest import next_phone


class UserFactory(factory.Factory):
    """用户工厂（build 模式，由调用方入库）。"""

    class Meta:
        model = User

    phone = factory.LazyFunction(next_phone)
    nickname = factory.Sequence(lambda n: f"测试用户{n}")
    role = UserRole.STUDENT
    is_k12 = False
    is_active = True
    password_hash = factory.LazyFunction(lambda: hash_password("password123"))


class QuestionFactory(factory.Factory):
    """题目工厂。"""

    class Meta:
        model = Question

    subject = "math"
    stage = "junior"
    qtype = QuestionType.CHOICE
    stem = factory.Sequence(lambda n: f"测试题干 {n}：下列哪个选项正确？")
    options = factory.LazyFunction(lambda: {"A": "1", "B": "2", "C": "3", "D": "4"})
    answer = "A"
    analysis = "解析：选 A。"
    difficulty = 3
    source = "self-built"
    status = QuestionStatus.PUBLISHED
    version = 1
