import csv
from django.utils.text import slugify
from .models import Course, Topic, SubTopic, Question, Option, Syllabus

REQUIRED_COLUMNS = [
    'course', 'topic', 'subtopic', 'question_type',
    'question', 'option_a', 'option_b', 'option_c', 'option_d',
    'correct_answer', 'reason', 'level'
]

# Optional columns for advanced math/science support
ADVANCED_COLUMNS = [
    'formula', 'symbol_type', 'latex_formula', 'image_url'
]

VALID_QUESTION_TYPES = {'theory', 'image', 'theory_image'}
VALID_CORRECT_ANSWERS = {'A', 'B', 'C', 'D'}
VALID_SYMBOL_TYPES = {'math', 'physics', 'chemistry', 'biology'}


def _decode_csv_file(file_obj):
    """
    Robustly decodes a CSV file object into a string.
    Tries UTF-8 first, then Latin-1, and finally ignores errors if needed.
    Also detects if the file is actually an Excel (.xlsx) file.
    """
    try:
        # Read the raw bytes
        raw_data = file_obj.read()
        
        # Reset pointer for future reads
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
            
        # Detect Excel/ZIP signature (PK\x03\x04)
        if raw_data.startswith(b'PK\x03\x04'):
            raise ValueError(
                "This file appears to be an Excel (.xlsx) workbook, not a plain text CSV. "
                "Please 'Save As' CSV (Comma Delimited) in Excel before uploading."
            )
            
        # Handle cases where file_obj is already a string
        if isinstance(raw_data, str):
            return raw_data
            
        # Try UTF-8 first
        try:
            return raw_data.decode('utf-8')
        except UnicodeDecodeError:
            # Fallback to Latin-1 which covers 0x87 and other legacy bytes
            try:
                return raw_data.decode('latin-1')
            except Exception:
                # Last resort: decode with utf-8 but ignore problematic bytes
                return raw_data.decode('utf-8', errors='ignore')
                
    except ValueError:
        # Re-raise our custom validation error
        raise
    except Exception as e:
        # If all else fails, return empty or try to stringify
        return str(file_obj)


def import_questions_from_csv(file_obj, created_by=None):
    import io
    content = _decode_csv_file(file_obj)
    reader = csv.DictReader(io.StringIO(content))
    inserted = 0
    skipped = 0
    errors = 0
    error_details = []

    for row_num, row in enumerate(reader, start=2):
        try:
            # Strip whitespace from all values and handle potential BOM
            row = {k.strip().replace('\ufeff', ''): v.strip() for k, v in row.items() if k}

            # Validate required columns
            missing = [col for col in REQUIRED_COLUMNS if col not in row]
            if missing:
                raise ValueError(f"Missing columns: {', '.join(missing)}")

            course_name   = row['course']
            topic_name    = row['topic']
            subtopic_name = row['subtopic']
            syllabus_name = row.get('syllabus', '').strip()
            question_type = row['question_type'].lower()
            question_body = row['question']
            option_a      = row['option_a']
            option_b      = row['option_b']
            option_c      = row['option_c']
            option_d      = row['option_d']
            correct_answer = row['correct_answer'].upper()
            reason        = row['reason']
            level_str     = row['level']
            difficulty    = row.get('difficulty', 'medium').lower()

            # Advanced fields
            formula       = row.get('formula', '')
            symbol_type   = row.get('symbol_type', '').lower()
            latex_formula = row.get('latex_formula', '')
            image_url_ext = row.get('image_url', '')

            # Validate fields
            if not question_body:
                raise ValueError("Question body is empty")
            if question_type not in VALID_QUESTION_TYPES:
                raise ValueError(f"Invalid question_type: {question_type}")
            if correct_answer not in VALID_CORRECT_ANSWERS:
                raise ValueError(f"Invalid correct_answer: {correct_answer}")
            
            if symbol_type and symbol_type not in VALID_SYMBOL_TYPES:
                # If invalid symbol type, just clear it instead of failing
                symbol_type = ''

            try:
                level = int(level_str)
                if not (1 <= level <= 5):
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValueError(f"Level must be integer 1–5, got: {level_str}")

            # Resolve syllabus (optional)
            syllabus = None
            if syllabus_name:
                syllabus = Syllabus.objects.filter(name__iexact=syllabus_name).first()
                if not syllabus:
                    raise ValueError(f"Syllabus '{syllabus_name}' not found. Create it first.")

            # Get or create Course (scoped by syllabus if provided)
            course_defaults = {'slug': _unique_slug(Course, course_name)}
            if syllabus:
                course_defaults['syllabus'] = syllabus
                course, _ = Course.objects.get_or_create(
                    name=course_name, syllabus=syllabus,
                    defaults=course_defaults
                )
            else:
                course, _ = Course.objects.get_or_create(
                    name=course_name,
                    defaults=course_defaults
                )

            # Get or create Topic
            topic_slug = _unique_slug(Topic, topic_name, course=course)
            topic, _ = Topic.objects.get_or_create(
                course=course,
                name=topic_name,
                defaults={'slug': topic_slug}
            )

            # Get or create SubTopic
            subtopic_slug = _unique_slug(SubTopic, subtopic_name, topic=topic)
            subtopic, _ = SubTopic.objects.get_or_create(
                topic=topic,
                name=subtopic_name,
                defaults={'slug': subtopic_slug}
            )

            # Skip duplicate questions
            if Question.objects.filter(subtopic=subtopic, body=question_body).exists():
                skipped += 1
                continue

            # Create Question
            question = Question.objects.create(
                subtopic=subtopic,
                created_by=created_by,
                question_type=question_type,
                body=question_body,
                explanation=reason,
                level=level,
                difficulty=difficulty,
                formula=formula,
                symbol_type=symbol_type,
                latex_formula=latex_formula,
                image_url_extra=image_url_ext
            )

            # Create Options
            options_map = {'A': option_a, 'B': option_b, 'C': option_c, 'D': option_d}
            for label, text in options_map.items():
                Option.objects.create(
                    question=question,
                    label=label,
                    text=text,
                    is_correct=(label == correct_answer)
                )

            inserted += 1

        except Exception as e:
            errors += 1
            error_details.append(f"Row {row_num}: {e}")

    return {
        'inserted': inserted,
        'skipped': skipped,
        'errors': errors,
        'error_details': error_details,
    }


def _unique_slug(model, name, **parent_kwargs):
    base_slug = slugify(name)
    slug = base_slug
    counter = 1
    qs = model.objects.filter(slug=slug, **parent_kwargs)
    while qs.exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
        qs = model.objects.filter(slug=slug, **parent_kwargs)
    return slug


# ─── SIMPLE FORMAT: question, answer, description ─────────────────────────────

SIMPLE_COLUMNS = ['question', 'answer', 'description']


def import_simple_csv(file_obj, subtopic_id, level=1, difficulty='medium', created_by=None):
    """
    Simple CSV format:
        question  — full question text
        answer    — the correct answer text (will become Option A, marked correct)
        description — explanation shown after answer

    All questions go into the given subtopic at the given level.
    Options are auto-generated:
        A = correct answer (from 'answer' column)
        B, C, D = left blank (staff can edit later)
    """
    from .models import SubTopic

    subtopic = SubTopic.objects.get(pk=subtopic_id)
    import io
    content = _decode_csv_file(file_obj)
    reader = csv.DictReader(io.StringIO(content))
    inserted = 0
    skipped = 0
    errors = 0
    error_details = []

    for row_num, row in enumerate(reader, start=2):
        try:
            row = {k.strip().lower(): v.strip() for k, v in row.items() if k}

            # Accept flexible column names
            question_body = (
                row.get('question') or row.get('question text') or
                row.get('q') or ''
            ).strip()
            answer_text = (
                row.get('answer') or row.get('correct answer') or
                row.get('ans') or ''
            ).strip()
            description = (
                row.get('description') or row.get('explanation') or
                row.get('reason') or row.get('desc') or ''
            ).strip()

            if not question_body:
                raise ValueError("Question text is empty")
            if not answer_text:
                raise ValueError("Answer text is empty")

            # Skip duplicates
            if Question.objects.filter(subtopic=subtopic, body=question_body).exists():
                skipped += 1
                continue

            # Create question
            q = Question.objects.create(
                subtopic=subtopic,
                created_by=created_by,
                body=question_body,
                explanation=description,
                level=level,
                difficulty=difficulty,
                question_type='theory',
            )

            # Option A = correct answer; B/C/D = placeholder
            Option.objects.create(question=q, label='A', text=answer_text, is_correct=True)
            Option.objects.create(question=q, label='B', text='Option B', is_correct=False)
            Option.objects.create(question=q, label='C', text='Option C', is_correct=False)
            Option.objects.create(question=q, label='D', text='Option D', is_correct=False)

            inserted += 1

        except Exception as e:
            errors += 1
            error_details.append(f"Row {row_num}: {e}")

    return {
        'inserted': inserted,
        'skipped': skipped,
        'errors': errors,
        'error_details': error_details,
    }


# ─── SECTION FORMAT: question, answer, section_number, description ────────────

SECTION_COLUMNS = ['question', 'answer', 'section_number', 'description']


def import_section_csv(file_obj, topic_id, level=1, difficulty='medium', created_by=None):
    """
    CSV columns (header required):
      question, answer, section_number, description

    section_number:
      Maps to SubTopic.order within the given Topic (topic_id).
      If the sub-topic for that section_number doesn't exist, it's created
      as: "Section {section_number}".
    """
    from .models import Topic, SubTopic

    topic = Topic.objects.get(pk=topic_id)
    import io
    content = _decode_csv_file(file_obj)
    reader = csv.DictReader(io.StringIO(content))
    inserted = 0
    skipped = 0
    errors = 0
    error_details = []

    for row_num, row in enumerate(reader, start=2):
        try:
            row = {k.strip().lower(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}

            question_body = (row.get('question') or row.get('q') or '').strip()
            answer_text = (row.get('answer') or row.get('ans') or '').strip()
            description = (row.get('description') or row.get('explanation') or row.get('reason') or '').strip()
            section_raw = (row.get('section_number') or row.get('section') or row.get('section no') or row.get('section_no') or '').strip()

            if not question_body:
                raise ValueError("Question text is empty")
            if not answer_text:
                raise ValueError("Answer text is empty")
            try:
                section_number = int(section_raw)
            except Exception:
                raise ValueError(f"Invalid section_number: {section_raw}")

            subtopic = SubTopic.objects.filter(topic=topic, order=section_number).first()
            if not subtopic:
                base_name = f"Section {section_number}"
                subtopic = SubTopic.objects.create(
                    topic=topic,
                    name=base_name,
                    slug=_unique_slug(SubTopic, base_name, topic=topic),
                    order=section_number,
                )

            # Skip duplicates
            if Question.objects.filter(subtopic=subtopic, body=question_body).exists():
                skipped += 1
                continue

            q = Question.objects.create(
                subtopic=subtopic,
                created_by=created_by,
                body=question_body,
                explanation=description,
                level=level,
                difficulty=difficulty,
                question_type='theory',
            )

            Option.objects.create(question=q, label='A', text=answer_text, is_correct=True)
            Option.objects.create(question=q, label='B', text='Option B', is_correct=False)
            Option.objects.create(question=q, label='C', text='Option C', is_correct=False)
            Option.objects.create(question=q, label='D', text='Option D', is_correct=False)

            inserted += 1

        except Exception as e:
            errors += 1
            error_details.append(f"Row {row_num}: {e}")

    return {
        'inserted': inserted,
        'skipped': skipped,
        'errors': errors,
        'error_details': error_details,
    }
