from app import db, bcrypt


class summary_config_count(db.Model):
    id = db.Column(db.Integer, primary_key=True, unique=True)
    config_count = db.Column(db.Integer, unique=False)
    last_update = db.Column(db.String, unique=False)


class summary_diff_count(db.Model):
    id = db.Column(db.Integer, primary_key=True, unique=True)
    diff_count = db.Column(db.Integer, unique=False)
    last_update = db.Column(db.String, unique=False)


class summary_match_count(db.Model):
    id = db.Column(db.Integer, primary_key=True, unique=True)
    match_count = db.Column(db.Integer, unique=False)
    last_update = db.Column(db.String, unique=False)


class summary_average_diffs(db.Model):
    id = db.Column(db.Integer, primary_key=True, unique=True)
    average_diffs = db.Column(db.Integer, unique=False)
    last_update = db.Column(db.String, unique=False)


class summary_changes(db.Model):
    id = db.Column(db.Integer, primary_key=True, unique=True)
    name = db.Column(db.String, unique=False)
    type = db.Column(db.String, unique=False)
    diffs = db.Column(db.String, unique=False)

class summary_assignments(db.Model):
    id = db.Column(db.Integer, primary_key=True, unique=True)
    name = db.Column(db.String, unique=False)
    type = db.Column(db.String, unique=False)
    membership_rule = db.Column(db.String, unique=False)
    assigned_to = db.Column(db.String, unique=False)


class backup_feed(db.Model):
    id = db.Column(db.Integer, primary_key=True, unique=True)
    feed = db.Column(db.String)


class update_feed(db.Model):
    id = db.Column(db.Integer, primary_key=True, unique=True)
    feed = db.Column(db.String)


class api_key(db.Model):
    id = db.Column(db.Integer, primary_key=True, unique=True)
    key_hash = db.Column(db.String(length=500), unique=True)
    key_expiration = db.Column(db.DateTime, unique=True)

    @property
    def key(self):
        return self.key

    @key.setter
    def key(self, plain_text_key):
        self.key_hash = bcrypt.generate_password_hash(plain_text_key).decode("utf-8")

    def check_key_correction(self, attempted_key):
        return bcrypt.check_password_hash(self.key_hash, attempted_key)


db.create_all()
db.session.commit()
