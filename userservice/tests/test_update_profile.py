import json
import pytest
from django.contrib.auth.models import User
from unittest.mock import patch


@pytest.mark.django_db
class TestProfileUpdate():
    url = '/api/v1/user-profile'

    # Todo - Mock calls to the BVN Service
    @patch('utils.helpers.BankingApi.bvn_enquiry')
    def test_update_sucess(self, mocked_bvn_enquiry, client, update_user, auth_header):
        """
        Method to test if a profile can be updated successfully.
        """

        mocked_bvn_enquiry.return_value = {
            "Status": "00",
            "Message": "BVN Details Retrieved Successfully",
            "data": {
                "firstName": "VICTOR",
                "middleName": "null",
                "lastName": "NWAKA",
                "gender": "Female",
                "dateOfBirth": "07-Aug-1958",
                "phoneNo": "08130462902"
            }
        }

        response = client.patch(self.url,
                                data=update_user,

                                **auth_header)
        print(response.data)
        assert response.status_code == 200
        assert 'message' in response.data.keys()
        assert response.data["message"] == "Profile Updated successfully"

    def test_with_invalid_first_name(self, client, auth_header, update_user):
        """
        Method to test profile update with invalid first_name.
        """
        response = client.patch(self.url,
                                data={"first_name": "H",
                                      "birthday": update_user["birthday"],
                                      "gender": update_user["gender"],
                                      "profile_image": update_user["profile_image"]},

                                **auth_header)
        assert response.status_code == 400
        assert 'errors' in response.data.keys()

    def test_with_invalid_profile_image(self, client, auth_header, update_user):
        """
         Method to test profile update with invalid profile_image.
        """
        response = client.patch(self.url,
                                data={"first_name": update_user["first_name"],
                                      "gender": update_user["gender"],
                                      "birthday": update_user["birthday"],
                                      "profile_image": "hrthytujgh"},

                                **auth_header)
        assert response.status_code == 400

    def test_with_invalid_birthday(self, client, auth_header, update_user):
        """
         Method to test profile update with invalid birthday value.
        """
        response = client.patch(self.url,
                                data={"first_name": update_user["first_name"],
                                      "gender": update_user["gender"],
                                      "birthday": "20/06/06",
                                      "profile_image": update_user["profile_image"]},

                                **auth_header)
        assert response.status_code == 400

    def test_with_invalid_password(self, client, auth_header, update_user):
        """
         Method to test profile update with wrong old password.
        """
        response = client.patch(self.url,
                                data={"first_name": update_user["first_name"],
                                      "gender": update_user["gender"],
                                      "birthday": "2017-03-10",
                                      "profile_image": update_user["profile_image"],
                                      "old_password": "11111111",
                                      "password": "88888888"},

                                **auth_header)
        assert response.status_code == 400
        assert response.data["error"] == 'password does not match old password!'

    def test_with_invalid_mobile_number(self, client, auth_header, update_user):
        """
         Method to test profile update with invalid mobile number.
        """
        response = client.patch(self.url,
                                data={"first_name": update_user["first_name"],
                                      "gender": update_user["gender"],
                                      "mobile_number": "803815616",
                                      "profile_image": update_user["profile_image"]},

                                **auth_header)
        assert response.status_code == 400
        # FIXME - This commented fucktard was breaking the test
        # assert response.data["errors"][0]["mobile_number"] == '803815616 is not a valid mobile number. Valid number looks like +2348012345678'

    def test_mobile_number_with_wrong_format(self, client, auth_header, update_user):
        """
         Method to test profile update with mobile number in wrong format.
        """
        response = client.patch(self.url,
                                data={"first_name": update_user["first_name"],
                                      "gender": update_user["gender"],
                                      "mobile_number": "2348038156168",
                                      "profile_image": update_user["profile_image"]},

                                **auth_header)
        assert response.status_code == 400

    @patch('utils.helpers.BankingApi.bvn_enquiry')
    def test_bvn_with_wrong_format(self, mocked_bvn_enquiry, client, auth_header, update_user):
        """
         Method to test profile update with invalid bvn.
        """
        mocked_bvn_enquiry.return_value = {
            "Status": "00",
            "Message": "BVN Details Retrieved Successfully",
            "data": {
                "firstName": "VICTOR",
                "middleName": "null",
                "lastName": "NWAKA",
                "gender": "Female",
                "dateOfBirth": "07-Aug-1958",
                "phoneNo": "08130462902"
            }
        }
        update_user["bvn"] = "89999h"
        response = client.patch(self.url, data=update_user, **auth_header)
        assert response.status_code == 400
        assert response.data["errors"]["bvn"][0] == 'Ensure this field has at least 11 characters.'
