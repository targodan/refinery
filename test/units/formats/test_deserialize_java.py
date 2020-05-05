#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import json

from .. import TestUnitBase


class TestJavaDeserializer(TestUnitBase):

    def test_serialized_rsa_key(self):
        data = bytes.fromhex(
            'ACED0005737200146A6176612E73656375726974792E4B6579526570BDF94FB3889AA543'
            '0200044C0009616C676F726974686D7400124C6A6176612F6C616E672F537472696E673B'
            '5B0007656E636F6465647400025B424C0006666F726D617471007E00014C000474797065'
            '74001B4C6A6176612F73656375726974792F4B657952657024547970653B787074000352'
            '5341757200025B42ACF317F8060854E00200007870000004C1308204BD020100300D0609'
            '2A864886F70D0101010500048204A7308204A302010002820101009ACA7722831F3A14EF'
            '5E250790C5C4D64A5878916E0EA0B4025BCCC7DBB160ED8CB7FA1E97F73537578BA96DD1'
            '178AE6EDECA01408751556D90C3F19A5667E6A8E1D29005D75A38911E69E9B0A0DD4963A'
            '34147333B5A2CC3D8ED86B80783A516519B5E8C964E22575A010771A32D276092B07FBC7'
            '550BDB11CE895B9698D90D93FBE5BB36D5D0AFE6102415E6B1D1B1FE40B07463BF373562'
            'E37E649E2EADEBECACA1A889AC40BE9049938881655E3240753E58E64E61DB37ECE214DE'
            '55492980DC1D68A3FA98C8E9D0E565B056C68B2AAE06884BB0BB02F3C21EF781E484756F'
            'D805DFFC78C4FE394CE8FFDDB40329C83AFD90B3A7E3C6152D7595A9A264B90203010001'
            '02820100761F6362B6E53191A0491BC0F63DB5C441DFD9C2415670546E2857D17C59943A'
            '3354824EAE713BEF0BA3CC9BBD2056237C1542E386C0B2941FF6348101B3816D171E3197'
            'D1BA601DCDC74BE9CC7659707AE21B68FE60F1E72262CBCCDDB0E1F01352D77AD9955EEE'
            '6F20C2EFE0D23FC14BA5C6E5E06B8A2C971E21BBFEE48D5D94CAA97A18D988550EBDB4F6'
            '7EE33F6C7D727B517DC588580BB7D70BD81613A3C9CCA5C3CBC54589F437644A984E5E03'
            'D80A2BAB5DB239CB3D25F13E93C0801CA2619F64C63359528346753254E2429D63A5371A'
            '9C6BF2604A987420CBF6782B72D871DD49C2FF46FE2C55159EB36438B87B4E45DF2F755D'
            '6EB8DFF09C00EE0102818100F532DB0E70FDD3C20D3DDC412884C7F165938CB71DB8B668'
            '6B25006B9CE57F75613AF2E8040A2867997CEB90C5B0B70EF068F5BD19D21B648F585662'
            '17B21CDB7CC129FA49356D5AB64DB3F78C176C9D8D444A3FBB8BCA6AFA11C5BB6F4F1228'
            'DA03275E3395F42B21A673AA07C9C347AD42475E09DFCE24909080219B98B6E902818100'
            'A19C1119A5BD9C2BC9F13D8D2EE71FD36895EABCA21B5B3DC3C229D7981873C2FDC65430'
            '3F270879B8C605044D4753138E8C50DA28AD369BB94D672B0A9E911E469E05F81F8E3CC8'
            'A8372AAB5F36727AC76F5F5E4F5E566F7DBA97B7DD4FB529359962AA2F189E72182F9FEF'
            '17BCBD2B718A4147755BC9F88EA25482F6033D5102818100AE5459007C7F4B0625A9FCA5'
            'EAEBF4C801431581BFC4EB1374521B69676497E95996B2CB18CC2C0BF449A7A60797EB9E'
            'D8789776BA1BF2D3DD429E3021CEC5CB9B782EA33F5798072DA43336E6486535E3115184'
            'DC8FB7FBB50DDBBAB699CE3C733C58CA15FD205B6612551BE76BA0C69E3D884628D91154'
            '57E014E9501A14B90281807AA0315984A99B169EE4AE0FB2C72D1EFCFCC460DDA0645B39'
            '6EDAD0FC57917F239099D1021A5C14006040EE42B51C147AD57D840BD962D64684B503B3'
            'CB1DD21B434CC4392D7471CD320EEE7A10964D13872E96212333F2E533F06B534267F41C'
            'F786261C165223C0B66264C95E2D2C09BB1E4D5A7F8B814EB95DE70144F40102818042C7'
            '598BD90681B41B987CD066914FD72058AED227CEEE3D257D6C8C9ED2B0EA6B9A11847BF0'
            '4A87ADE43CF03FE8C228D4DA3B205C51F6BBC0C827F641176A6B80FD6C750DE23043752F'
            'C1A8EEAE2AC83ED5B1E77EDF0FB0129FBB37EC4B3061D42D481A94B9D19CE99487CF66DB'
            'BB0EE03F53EB08B66772BC5D20795B60BCC2740006504B435323387E7200196A6176612E'
            '73656375726974792E4B6579526570245479706500000000000000001200007872000E6A'
            '6176612E6C616E672E456E756D0000000000000000120000787074000750524956415445'
        )

        logging.StreamHandler.terminator = ', '

        unit = self.load()
        jser = json.loads(unit(data))

        self.assertEqual(jser['fields']['algorithm'], 'RSA')
        self.assertEqual(jser['fields']['type'], 'PRIVATE')
        self.assertGreater(len(jser['fields']['encoded']), 1000)
        self.assertIn(bytes(jser['fields']['encoded']), data)
