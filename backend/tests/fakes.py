"""测试替身：不加载真实向量模型。"""

from app.rag.embedding import EmbeddingError


class FakeEmbedder:
    """按关键词生成固定向量，让检索结果可预测。"""

    dimension = 7
    KEYS = ("寄养", "疫苗", "换粮", "测试甲", "测试乙", "测试丙")

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [
            [1.0 if key in text else 0.0 for key in self.KEYS] + [0.01]
            for text in texts
        ]


class BrokenEmbedder:
    dimension = 7

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingError("测试环境模拟模型不可用")
