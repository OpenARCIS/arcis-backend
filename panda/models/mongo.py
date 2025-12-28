from typing import Annotated
from pydantic import BeforeValidator, BaseModel, Field
from typing import Optional

# convert _id which is ObjectID (from motor) into str
PyObjectId = Annotated[str, BeforeValidator(str)]

class MongoBaseModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    class Config:
        populate_by_name = True # for using class var names instead of mongo var names
