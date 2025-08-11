from flask_sqlalchemy import SQLAlchemy

# Instância global do SQLAlchemy
db = SQLAlchemy()

class WikiDocument(db.Model):
    __tablename__ = 'wiki_documents'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, unique=True)
    url = db.Column(db.String(500), nullable=False, unique=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # Relacionamento com chunks (1 documento tem muitos chunks)
    chunks = db.relationship('WikiChunk', backref='document', cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<WikiDocument {self.title}>'

class WikiChunk(db.Model):
    __tablename__ = 'wiki_chunks'
    
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('wiki_documents.id'), nullable=False)
    chunk_text = db.Column(db.Text, nullable=False)
    chunk_index = db.Column(db.Integer, nullable=False)
    embedding_id = db.Column(db.String, nullable=True)
    embedding = db.Column(db.PickleType, nullable=True)  # Vetor do embedding
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    
    def __repr__(self):
        return f'<WikiChunk {self.id} doc_id={self.document_id}>'
