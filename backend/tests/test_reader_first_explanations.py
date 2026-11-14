"""User-facing wording must explain the screening category without invented forensics."""
import io

import pymupdf
from PIL import Image
from app.narrative_service import (
    reader_overall_explanation, reader_method_explanation, reader_comparison_explanation,
)
from app.report_service import generate_forensic_report


def _png():
    buf = io.BytesIO()
    Image.new('RGB', (224, 224), 'gray').save(buf, 'PNG')
    return buf.getvalue()


def _entry(target, support=(), oppose=()):
    return {
        'status':'completed','target_label':target,
        'interpretation': {
            'regions': {'supporting':list(support), 'opposing':list(oppose)},
            'narrative':'For the Fake-category output, Grad-CAM showed stronger CNN activation.',
        },
    }


def _case(label='Fake', fake=.54916643):
    return {'prediction':label, 'fake_probability':fake, 'threshold':.5,
        'confidence': fake if label=='Fake' else 1-fake,
        'model':'FourModelStacking','analysis_id':'ai123',
        'xai':{
            'gradcam':_entry(label, ['outside estimated face/head regions', 'lower crop / neck-clothing vicinity (approximate)']),
            'lime':_entry(label,['person\'s left cheek'],['nose']),
            'shap':_entry(label,['person\'s left cheek']),
        }}


def test_fake_user_text_leads_with_result_and_near_threshold():
    text=reader_overall_explanation(_case())
    assert text.startswith('The AI classified this image as FAKE')
    assert '54.9%' in text and '50.0%' in text
    assert 'close to the decision cutoff' in text
    assert 'areas around the face and head' in text


def test_real_user_text_never_authenticates_image():
    text=reader_overall_explanation(_case('Real',.28))
    assert text.startswith('The AI classified this image as REAL')
    assert 'does not verify' in text
    explanation=reader_method_explanation('lime',_case('Real',.28))
    assert 'toward Real' in explanation
    assert 'person\'s left cheek' in explanation


def test_class_mismatch_fails_closed():
    r=_case('Real',.2)
    r['xai']['lime']['target_label']='Fake'
    text=reader_method_explanation('lime',r)
    assert 'earlier Fake result' in text
    assert 'mouth' not in text


def test_missing_regions_do_not_invent_diagnosis():
    r=_case()
    r['xai']['gradcam']['interpretation']['regions']={'supporting':[]}
    text=reader_method_explanation('gradcam',r)
    assert 'did not single out' in text
    assert 'edited mouth' not in text


def test_pdf_reader_first_and_cautions_after():
    b=_png()
    pdf=generate_forensic_report(_case(), {'filename':'sample.png','sha256':'a'*64,'width':224,'height':224}, b,b,lime_png=b,shap_png=b)
    assert pdf.startswith(b'%PDF')
    with pymupdf.open(stream=pdf,filetype='pdf') as doc:
        text='\n'.join(page.get_text() for page in doc)
    assert 'The AI classified this image as FAKE' in text
    assert '54.9%' in text
    assert 'neck or clothing' in text
    assert 'Technical methodology and limitations' in text
    assert text.index('The AI classified this image as FAKE') < text.index('Technical methodology and limitations')
    assert 'This is a Fake-category map of the four CNNs' not in text


def test_comparison_only_claims_overlapping_saved_regions():
    text=reader_comparison_explanation(_case())
    assert 'More than one explanation highlighted' in text
    assert 'left cheek' in text
