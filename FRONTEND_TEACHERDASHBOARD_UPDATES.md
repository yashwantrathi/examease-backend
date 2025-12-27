# TeacherDashboard.jsx - Manual Question Addition Feature

## Changes Required

Add these state variables after the existing exam creation states (around line 41):

```javascript
  // Manual Question Creation
  const [manualQType, setManualQType] = useState("mcq");
  const [manualQuestion, setManualQuestion] = useState("");
  const [manualOptions, setManualOptions] = useState(["", "", "", ""]);
  const [manualAnswer, setManualAnswer] = useState("");
  const [manualMarks, setManualMarks] = useState(1);
```

## Add these helper functions before renderMenu():

```javascript
  const addManualQuestion = () => {
    if (!manualQuestion.trim()) {
      alert("Please enter a question");
      return;
    }

    if (manualQType === "mcq") {
      const validOptions = manualOptions.filter(o => o.trim());
      if (validOptions.length < 4) {
        alert("MCQ must have 4 options");
        return;
      }
      if (!manualAnswer.trim() || !manualOptions.includes(manualAnswer)) {
        alert("Please select a valid answer from the options");
        return;
      }
    } else {
      if (!manualAnswer.trim()) {
        alert("Please provide the correct answer");
        return;
      }
    }

    const newQuestion = {
      id: questions.length + 1,
      type: manualQType,
      question: manualQuestion,
      options: manualQType === "mcq" ? manualOptions : null,
      answer: manualAnswer,
      marks: manualMarks
    };

    setQuestions([...questions, newQuestion]);
    
    // Reset form
    setManualQuestion("");
    setManualOptions(["", "", "", ""]);
    setManualAnswer("");
    setManualMarks(1);
    
    alert("✅ Question added!");
  };

  const updateManualOption = (index, value) => {
    const newOptions = [...manualOptions];
    newOptions[index] = value;
    setManualOptions(newOptions);
  };
```

## Replace the renderCreate() function with this updated version:

```javascript
  const renderCreate = () => (
    <div className="section-card">
      <div className="section-header">
        <h2>Create Exam</h2>
        <button className="btn-ghost" onClick={() => setView("menu")}>
          Back
        </button>
      </div>

      <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 30}}>
        <div>
          <h3>Exam Details</h3>
          
          <input 
            className="input-pill"
            placeholder="Exam Title (e.g., Physics Midterm)"
            value={topic}
            onChange={e => setTopic(e.target.value)}
          />

          <input 
            className="input-pill"
            placeholder="Subject (e.g., Physics)"
            value={subject}
            onChange={e => setSubject(e.target.value)}
            style={{marginTop: 10}}
          />

          <div style={{display: 'flex', gap: 10, marginTop: 10}}>
            <div style={{flex: 1}}>
              <label style={{fontSize: '0.9rem', color: '#6b7280'}}>Questions</label>
              <input 
                type="number"
                className="input-pill"
                value={numQuestions}
                onChange={e => {
                  const val = parseInt(e.target.value) || 0;
                  setNumQuestions(Math.max(1, Math.min(50, val)));
                }}
                min="1"
                max="50"
              />
            </div>
            <div style={{flex: 1}}>
              <label style={{fontSize: '0.9rem', color: '#6b7280'}}>Duration (mins)</label>
              <input 
                type="number"
                className="input-pill"
                value={duration}
                onChange={e => {
                  const val = parseInt(e.target.value) || 0;
                  setDuration(Math.max(1, val));
                }}
                min="1"
              />
            </div>
          </div>

          {/* OPTION 1: AI GENERATION FROM PDF */}
          <div style={{marginTop: 20}}>
            <label style={{fontSize: '0.9rem', color: '#6b7280', fontWeight: 600}}>
              Option 1: Generate from PDF
            </label>
            <label className="upload-pill" style={{marginTop: 10, width: '100%'}}>
              Upload PDF and Generate (Max 10MB)
              <input 
                type="file" 
                accept=".pdf"
                onChange={handleAIGenerate}
                hidden
              />
            </label>
          </div>

          {/* OPTION 2: MANUAL QUESTION CREATION */}
          <div style={{marginTop: 25, padding: 15, background: '#f9fafb', borderRadius: 12, border: '1px solid #e5e7eb'}}>
            <label style={{fontSize: '0.9rem', color: '#6b7280', fontWeight: 600}}>
              Option 2: Add Questions Manually
            </label>
            
            <div style={{marginTop: 15}}>
              <label style={{fontSize: '0.85rem', color: '#6b7280'}}>Question Type</label>
              <select 
                className="input-pill"
                value={manualQType}
                onChange={e => setManualQType(e.target.value)}
                style={{marginTop: 5}}
              >
                <option value="mcq">Multiple Choice (MCQ)</option>
                <option value="subjective">Subjective (Open-ended)</option>
              </select>
            </div>

            <textarea 
              className="input-pill"
              placeholder="Enter question text"
              value={manualQuestion}
              onChange={e => setManualQuestion(e.target.value)}
              style={{marginTop: 10, minHeight: 60, fontFamily: 'inherit'}}
            />

            {manualQType === "mcq" ? (
              <div style={{marginTop: 10}}>
                <label style={{fontSize: '0.85rem', color: '#6b7280'}}>Options (A, B, C, D)</label>
                {manualOptions.map((opt, i) => (
                  <input 
                    key={i}
                    className="input-pill"
                    placeholder={`Option ${String.fromCharCode(65 + i)}`}
                    value={opt}
                    onChange={e => updateManualOption(i, e.target.value)}
                    style={{marginTop: 8}}
                  />
                ))}

                <div style={{marginTop: 10}}>
                  <label style={{fontSize: '0.85rem', color: '#6b7280'}}>Correct Answer</label>
                  <select 
                    className="input-pill"
                    value={manualAnswer}
                    onChange={e => setManualAnswer(e.target.value)}
                    style={{marginTop: 5}}
                  >
                    <option value="">Select answer</option>
                    {manualOptions.map((opt, i) => (
                      <option key={i} value={opt}>
                        {opt ? `${String.fromCharCode(65 + i)}: ${opt}` : `Option ${String.fromCharCode(65 + i)}`}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            ) : (
              <textarea 
                className="input-pill"
                placeholder="Enter the model/expected answer"
                value={manualAnswer}
                onChange={e => setManualAnswer(e.target.value)}
                style={{marginTop: 10, minHeight: 60, fontFamily: 'inherit'}}
              />
            )}

            <div style={{marginTop: 10}}>
              <label style={{fontSize: '0.85rem', color: '#6b7280'}}>Marks</label>
              <input 
                type="number"
                className="input-pill"
                value={manualMarks}
                onChange={e => setManualMarks(Math.max(1, parseInt(e.target.value) || 1))}
                min="1"
                style={{marginTop: 5}}
              />
            </div>

            <button 
              className="btn-primary"
              onClick={addManualQuestion}
              style={{marginTop: 15, width: '100%'}}
            >
              Add Question to Exam
            </button>
          </div>

          {savedExamId && (
            <div style={{
              marginTop: 20,
              padding: 15,
              background: '#f0fdf4',
              borderRadius: 12,
              border: '1px solid #bbf7d0'
            }}>
              <strong style={{color: '#166534'}}>✅ Exams Saved Successfully!</strong>
              
              <div style={{marginTop: 15}}>
                <p style={{fontSize: '0.9rem', color: '#166534', marginBottom: 5}}>
                  Main Exam Code:
                </p>
                <p style={{fontSize: '1.5rem', fontWeight: 800, margin: '5px 0', color: '#166534'}}>
                  {savedExamId}
                </p>
              </div>
              
              {savedDemoId && (
                <div style={{marginTop: 15}}>
                  <p style={{fontSize: '0.9rem', color: '#166534', marginBottom: 5}}>
                    Demo Exam Code:
                  </p>
                  <p style={{fontSize: '1.5rem', fontWeight: 800, margin: '5px 0', color: '#166534'}}>
                    {savedDemoId}
                  </p>
                </div>
              )}
              
              <p style={{fontSize: '0.9rem', color: '#166534', marginTop: 15}}>
                📋 Share these codes with your students
              </p>
              
              <button 
                className="btn-ghost btn-small"
                onClick={resetExamForm}
                style={{marginTop: 15, width: '100%'}}
              >
                Create Another Exam
              </button>
            </div>
          )}
        </div>

        <div>
          <h3>Questions in Exam ({questions.length})</h3>
          
          {questions.length === 0 ? (
            <div style={{textAlign: 'center', padding: 40, color: '#6b7280'}}>
              <p>Add questions by uploading PDF or manually entering them</p>
            </div>
          ) : (
            <div style={{maxHeight: 500, overflowY: 'auto'}}>
              {questions.map((q, i) => (
                <div key={i} className="question-card" style={{marginBottom: 15}}>
                  <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'start'}}>
                    <div style={{flex: 1}}>
                      <strong>Q{i + 1}:</strong> {q.question}
                      <div style={{marginTop: 10}}>
                        <span className={`pill-tag ${q.type === 'mcq' ? 'pill-tag-blue' : 'pill-tag-orange'}`}>
                          {q.type.toUpperCase()}
                        </span>
                      </div>
                    </div>
                    <button 
                      className="tiny-link"
                      onClick={() => deleteQuestion(i)}
                      style={{marginLeft: 10}}
                    >
                      Delete
                    </button>
                  </div>
                  
                  <div style={{marginTop: 10, display: 'flex', alignItems: 'center', gap: 10}}>
                    <label style={{fontSize: '0.9rem'}}>Marks:</label>
                    <input 
                      type="number"
                      value={q.marks}
                      onChange={e => updateQuestionMarks(i, e.target.value)}
                      style={{width: 60, padding: 5, borderRadius: 6, border: '1px solid #d1d5db'}}
                      min="1"
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          {questions.length > 0 && !savedExamId && (
            <button 
              className="btn-primary" 
              onClick={handleSaveExam}
              style={{marginTop: 15, width: '100%'}}
            >
              Save Exam
            </button>
          )}
        </div>
      </div>
    </div>
  );
```

## Summary of Changes

✅ **Two ways to create questions:**
- **Option 1**: Upload PDF → AI generates questions automatically
- **Option 2**: Manually enter questions one by one

✅ **Both methods can be mixed:**
- Upload PDF for some questions
- Add manual questions for others
- All combine in the final exam

✅ **Manual question form includes:**
- Question type toggle (MCQ/Subjective)
- Question text input
- Options for MCQ (4 fields)
- Answer selection
- Marks assignment

✅ **No backend changes needed** - Backend already supports both!

Copy these changes to your `examease-frontend/src/TeacherDashboard.jsx` file.
